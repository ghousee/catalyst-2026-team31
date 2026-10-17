"""RAG feasibility spike: reproduces every number in docs/RAG_SPIKE.md.

    python scripts/rag_spike.py --all
    python scripts/rag_spike.py --verify-gold --retrieval        # pieces: --generation --verifier --gate

Needs: docker compose up -d (db + ollama), manuals ingested (python -m backend.ingest.loader),
qwen3.5:4b + embeddinggemma pulled, .venv with requirements.txt. Results go to eval/results/rag_spike.json
(gitignored) and are printed as tables.
"""
import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psycopg  # noqa: E402
from pgvector.psycopg import register_vector  # noqa: E402

from backend import settings  # noqa: E402
from backend.ingest.embedder import embed_query  # noqa: E402
from backend.ingest.manuals import MANUALS  # noqa: E402
from backend.pipeline import gate, generate, llm, retrieve as R  # noqa: E402

EVAL = ROOT / "eval"
RESULTS = EVAL / "results" / "rag_spike.json"
VERSION_OF = {m.system_id: m.version_id for m in MANUALS}


def read_jsonl(name):
    return [json.loads(l) for l in (EVAL / name).read_text(encoding="utf-8").splitlines() if l.strip()]


def entry_hit(rid, golds):
    """Lenient match: the result is the gold chunk or a sibling chunk of the same manual entry
    (e.g. 'stop-tmf-part-2' or 'stop-tmf-output-displayed' for gold 'stop-tmf')."""
    for g in golds:
        base = re.sub(r"(-part-\d+|-\d+)$", "", g)
        if rid == g or rid.startswith(base + "-"):
            return True
    return False


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def ctx_for(system, version=None):
    return {"system": system, "version": version or VERSION_OF[system], "site": None}


def connect():
    conn = psycopg.connect(settings.DATABASE_URL)
    register_vector(conn)
    return conn


_qvec_cache = {}


def qvec(q):
    if q not in _qvec_cache:
        t = time.time()
        v = embed_query(q, cpu=True)
        _qvec_cache[q] = (v, time.time() - t)
    return _qvec_cache[q][0]


def table(headers, rows):
    w = [max(len(str(x)) for x in col) for col in zip(headers, *rows)]
    line = lambda r: "| " + " | ".join(str(x).ljust(n) for x, n in zip(r, w)) + " |"
    print(line(headers))
    print("|" + "|".join("-" * (n + 2) for n in w) + "|")
    for r in rows:
        print(line(r))
    print()


# ---------------------------------------------------------------- gold verification
def verify_gold(conn, out):
    bad = []
    for q in read_jsonl("spike_questions.jsonl"):
        for gid in q["gold"]:
            row = conn.execute("SELECT text, system_id FROM doc_chunk WHERE id=%s", (gid,)).fetchone()
            if not row:
                bad.append((q["id"], gid, "missing"))
            elif row[1] != q["system"]:
                bad.append((q["id"], gid, f"system {row[1]}"))
            elif q["must_contain"].lower() not in row[0].lower():
                bad.append((q["id"], gid, f"lacks '{q['must_contain']}'"))
    print("gold verification:", "OK, all gold chunks exist and contain their key phrase" if not bad else bad)
    out["gold_problems"] = bad
    return not bad


# ---------------------------------------------------------------- retrieval
def retrieval_configs(conn):
    """name -> fn(question_row, k) -> rows. Filter = the question's subsystem + that manual's series."""
    def mk(kind, filtered, version=None):
        def run(q, k):
            ctx = ctx_for(q["system"], version) if filtered else None
            if kind == "vec":
                return R.vector_search(conn, qvec(q["question"]), ctx, k)
            if kind == "kw":
                return R.keyword_search(conn, q["question"], ctx, k)
            return R.hybrid_search(conn, q["question"], qvec(q["question"]), ctx, k)
        return run
    return {
        "vector, no filter": mk("vec", False),
        "keyword, no filter": mk("kw", False),
        "hybrid, no filter": mk("hyb", False),
        "vector + subsystem filter": mk("vec", True),
        "keyword + subsystem filter": mk("kw", True),
        "hybrid + subsystem filter": mk("hyb", True),
        "hybrid + filter, WRONG series rvu:J for all": mk("hyb", True, "rvu:J"),
    }


def eval_retrieval(conn, out, k=5, depth=10):
    qs = read_jsonl("spike_questions.jsonl")
    for q in qs:
        qvec(q["question"])  # warm + cache query embeddings (CPU)
    res = {}
    rows = []
    for name, fn in retrieval_configs(conn).items():
        per, lat = [], []
        for q in qs:
            t = time.time()
            got = fn(q, depth)
            lat.append((time.time() - t) * 1000)
            ids = [r["id"] for r in got]
            rank = next((i + 1 for i, x in enumerate(ids) if x in q["gold"]), None)
            top = got[:k]
            wrong = sum(1 for r in top if r["system_id"] != q["system"])
            erank = next((i + 1 for i, x in enumerate(ids) if entry_hit(x, q["gold"])), None)
            per.append({"id": q["id"], "type": q["type"], "rank": rank, "erank": erank, "n": len(top),
                        "wrong": wrong, "top": ids[:k]})
        def agg(sel):
            sub = [p for p in per if sel(p)]
            if not sub:
                return None
            return {"n": len(sub), "recall@5": sum(1 for p in sub if p["rank"] and p["rank"] <= k) / len(sub),
                    "mrr": sum(1 / p["rank"] for p in sub if p["rank"]) / len(sub),
                    "entry_recall@5": sum(1 for p in sub if p["erank"] and p["erank"] <= k) / len(sub),
                    "entry_mrr": sum(1 / p["erank"] for p in sub if p["erank"]) / len(sub),
                    "contam": (sum(p["wrong"] for p in sub) / max(1, sum(p["n"] for p in sub)))}
        res[name] = {"all": agg(lambda p: True), "by_type": {t: agg(lambda p, t=t: p["type"] == t)
                     for t in ("syntax", "event", "fix", "trap")},
                     "latency_ms_p50": statistics.median(lat), "latency_ms_p95": pct(lat, 95), "per_question": per}
        a = res[name]["all"]
        rows.append([name, f"{a['recall@5']:.2f}", f"{a['mrr']:.3f}", f"{a['entry_recall@5']:.2f}",
                     f"{a['entry_mrr']:.3f}", f"{a['contam'] * 100:.0f}%",
                     f"{res[name]['latency_ms_p50']:.0f}"])
    print(f"== Retrieval ({len(qs)} questions, k={k}); contamination = % of top-{k} rows from a different subsystem")
    print("strict = gold chunk id(s); entry = gold or a sibling chunk of the same manual entry")
    table(["config", "recall@5", "MRR", "entry recall@5", "entry MRR", "wrong-subsystem rows", "db ms p50"], rows)
    types = ("syntax", "event", "fix", "trap")
    print("recall@5 / MRR by question type")
    table(["config"] + list(types),
          [[n] + [f"{r['by_type'][t]['recall@5']:.2f} / {r['by_type'][t]['mrr']:.2f}" for t in types] for n, r in res.items()])
    qlat = [v[1] * 1000 for v in _qvec_cache.values()]
    res["_query_embed_cpu_ms"] = {"p50": statistics.median(qlat), "p95": pct(qlat, 95), "max": max(qlat)}
    print(f"query embedding on CPU (embeddinggemma via Ollama): p50 {res['_query_embed_cpu_ms']['p50']:.0f} ms, "
          f"p95 {res['_query_embed_cpu_ms']['p95']:.0f} ms, max {res['_query_embed_cpu_ms']['max']:.0f} ms (max = cold model load)\n")
    out["retrieval"] = res


# ---------------------------------------------------------------- generation
def retrieve_for(conn, q, k=5):
    return R.hybrid_search(conn, q["question"], qvec(q["question"]), ctx_for(q["system"]), k)


GEN_IDS = ["q02", "q03", "q08", "q09", "q13", "q15", "q16", "q18", "q20", "q25"]


def eval_generation(conn, out, k=5, num_ctx=8192):
    qs = {q["id"]: q for q in read_jsonl("spike_questions.jsonl")}
    llm.chat([{"role": "user", "content": "ok"}], num_ctx=num_ctx, max_tokens=2)  # warm model, exclude load time
    out["generation"] = {}
    for alias in (False, True):
        mode = "S1..S5 aliases" if alias else "raw chunk ids"
        rows, stats, store = [], [], []
        for qid in GEN_IDS:
            q = qs[qid]
            chunks = retrieve_for(conn, q, k)
            claims, r = generate.generate(q["question"], chunks, num_ctx=num_ctx, alias=alias)
            valid = claims is not None
            kept, dropped = generate.keep_cited(claims, [c["id"] for c in chunks]) if valid else ([], [])
            cites_gold = any(c["source_id"] in q["gold"] for c in kept)
            stats.append({"id": qid, "valid_json": valid, "claims": len(claims or []), "cited_valid": len(kept),
                          "dropped": len(dropped), "cites_gold": cites_gold, "seconds": r["seconds"],
                          "prompt_tokens": r["prompt_tokens"], "gen_tokens": r["gen_tokens"],
                          "tok_per_s": r["tok_per_s"]})
            store.append({"id": qid, "question": q["question"], "claims": claims, "chunks": [c["id"] for c in chunks]})
            rows.append([qid, valid, len(claims or []), len(kept), cites_gold, f"{r['seconds']:.1f}",
                         r["prompt_tokens"], r["gen_tokens"], f"{r['tok_per_s']:.0f}"])
        ps = llm.loaded_models()
        total = sum(s["claims"] for s in stats)
        ok = sum(s["cited_valid"] for s in stats)
        secs = [s["seconds"] for s in stats]
        summary = {"mode": mode, "json_valid_rate": sum(s["valid_json"] for s in stats) / len(stats),
                   "claims_total": total, "claims_valid_source_rate": ok / total if total else None,
                   "answers_citing_gold_rate": sum(s["cites_gold"] for s in stats) / len(stats),
                   "latency_s_p50": statistics.median(secs), "latency_s_p95": pct(secs, 95),
                   "tok_per_s_mean": statistics.mean(s["tok_per_s"] for s in stats),
                   "prompt_tokens_mean": statistics.mean(s["prompt_tokens"] for s in stats),
                   "num_ctx": num_ctx, "ollama_ps": ps}
        print(f"== Generation ({mode}): Qwen {settings.LLM_MODEL}, hybrid+filter top-{k}, structured output, think=off")
        table(["q", "valid JSON", "claims", "valid cite", "cites gold", "sec", "prompt tok", "gen tok", "tok/s"], rows)
        print(json.dumps({k_: v for k_, v in summary.items() if k_ != "ollama_ps"}, indent=1))
        for m in ps:
            print(f"ollama ps: {m['name']} size {m['size'] / 2**30:.2f} GiB, in VRAM {m['size_vram'] / 2**30:.2f} GiB "
                  f"({100 * m['size_vram'] / m['size']:.0f}% GPU), context {m.get('context_length')}")
        print()
        out["generation"][mode] = {"summary": summary, "per_question": stats, "answers": store}


def probe_context(conn, out):
    """How much context fits: raise num_ctx and look at the GPU share in /api/ps."""
    q = {"question": "how do I stop a disk", "system": "sub:SCF-STORAGE"}
    chunks = retrieve_for(conn, q, 5)
    rows = []
    for n in (4096, 8192, 12288, 16384, 32768):
        try:
            r = llm.chat(generate.build_messages(q["question"], chunks), schema=generate.CLAIMS_SCHEMA, num_ctx=n)
            m = next((x for x in llm.loaded_models() if x["name"].startswith(settings.LLM_MODEL.split(":")[0])), None)
            gpu = f"{100 * m['size_vram'] / m['size']:.0f}%" if m else "?"
            rows.append([n, f"{m['size'] / 2**30:.2f}" if m else "?", gpu, f"{r['seconds']:.1f}", f"{r['tok_per_s']:.0f}"])
        except Exception as e:  # noqa: BLE001 - record and move on
            rows.append([n, "-", "-", f"ERR {type(e).__name__}", "-"])
    print("== Context-length probe (model size grows with num_ctx; GPU % must stay 100)")
    table(["num_ctx", "loaded GiB", "GPU %", "sec (incl. model reload)", "tok/s"], rows)
    out["context_probe"] = rows


# ---------------------------------------------------------------- verifier
def eval_verifier(conn, out, threshold=0.5):
    from backend.pipeline import verify
    pairs = read_jsonl("spike_claims.jsonl")
    verify.support_prob("warm up", "warm up")  # exclude model load
    rows, sup, uns, lat = [], [], [], []
    for p in pairs:
        text = conn.execute("SELECT text FROM doc_chunk WHERE id=%s", (p["chunk"],)).fetchone()[0]
        t = time.time()
        s = verify.support_prob(text, p["claim"])
        lat.append(time.time() - t)
        (sup if p["supported"] else uns).append(s)
        rows.append([p["id"], "S" if p["supported"] else "U", f"{s:.3f}", "keep" if s >= threshold else "drop", p["note"]])
    correct = sum(1 for s in sup if s >= threshold) + sum(1 for s in uns if s < threshold)
    # AUC by pairwise comparison
    auc = sum((a > b) + 0.5 * (a == b) for a in sup for b in uns) / (len(sup) * len(uns))
    summ = {"n": len(pairs), "supported_mean": statistics.mean(sup), "unsupported_mean": statistics.mean(uns),
            "accuracy@0.5": correct / len(pairs), "auc": auc, "latency_s_mean": statistics.mean(lat),
            "latency_s_p95": pct(lat, 95), "supported_min": min(sup), "unsupported_max": max(uns)}
    print("== MiniCheck-Flan-T5-Large on CPU (S = supported, U = deliberately unsupported)")
    table(["id", "label", "P(support)", f"@{threshold}", "note"], rows)
    print(json.dumps(summ, indent=1), "\n")
    out["verifier"] = {"summary": summ, "rows": rows}
    gen = out.get("generation", {}).get("S1..S5 aliases")
    if gen:  # score the claims Qwen actually wrote
        scores = []
        for a in gen["answers"]:
            for c in a["claims"] or []:
                if c["source_id"] in a["chunks"]:
                    text = conn.execute("SELECT text FROM doc_chunk WHERE id=%s", (c["source_id"],)).fetchone()[0]
                    scores.append(verify.support_prob(text, c["claim"]))
        if scores:
            out["verifier"]["on_generated_claims"] = {"n": len(scores), "mean": statistics.mean(scores),
                                                      "kept@0.5": sum(s >= threshold for s in scores) / len(scores)}
            print("MiniCheck on Qwen's own cited claims:", out["verifier"]["on_generated_claims"], "\n")


# ---------------------------------------------------------------- sufficiency gate
def eval_gate(conn, out, k=5):
    items = read_jsonl("spike_gate.jsonl")
    rows, correct, secs = [], 0, []
    for it in items:
        chunks = R.hybrid_search(conn, it["question"], qvec(it["question"]), ctx_for(it["system"]), k)
        verdict, r = gate.sufficient(it["question"], chunks)
        ok = verdict is it["answerable"]
        correct += ok
        secs.append(r["seconds"])
        rows.append([it["id"], it["answerable"], verdict, "ok" if ok else "WRONG", f"{r['seconds']:.1f}", it["question"][:60]])
    ans = [r for r in rows if r[1]]
    una = [r for r in rows if not r[1]]
    summ = {"accuracy": correct / len(items),
            "answerable_correct": sum(r[3] == "ok" for r in ans), "answerable_n": len(ans),
            "unanswerable_correct": sum(r[3] == "ok" for r in una), "unanswerable_n": len(una),
            "latency_s_p50": statistics.median(secs)}
    print("== Sufficiency gate (prompt-based Qwen, hybrid+filter top-5)")
    table(["id", "answerable", "gate said", "", "sec", "question"], rows)
    print(json.dumps(summ), "\n")
    out["gate"] = {"summary": summ, "rows": rows}


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for f in ("all", "verify-gold", "retrieval", "generation", "context", "verifier", "gate"):
        ap.add_argument(f"--{f}", action="store_true")
    a = ap.parse_args(argv)
    if not any(vars(a).values()):
        ap.error("pick at least one step, e.g. --all")
    out = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {}
    with connect() as conn:
        if a.all or a.verify_gold:
            verify_gold(conn, out)
        if a.all or a.retrieval:
            eval_retrieval(conn, out)
        if a.all or a.generation:
            eval_generation(conn, out)
        if a.all or a.context:
            probe_context(conn, out)
        if a.all or a.verifier:
            eval_verifier(conn, out)
        if a.all or a.gate:
            eval_gate(conn, out)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print("saved", RESULTS)


if __name__ == "__main__":
    main()
