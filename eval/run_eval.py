"""Golden-set eval harness.

Usage:
  python eval/run_eval.py                      # full pipeline, eval/golden.jsonl
  python eval/run_eval.py --config 1           # ablation: 1=plain RAG ... 4=full
  python eval/run_eval.py --golden eval/golden_template.jsonl

Expects the API at http://localhost:8000/chat (see docs/API_CONTRACT.md), which accepts
an optional "ablation" int for configs 1-4.

Contamination is computed from the DB, not from the API's own claims: every cited
source_id is looked up in doc_chunk/heuristic (DATABASE_URL) and compared with the
item's gold system. A citation whose source isn't in the DB counts as contaminated.
"""
import argparse, csv, json, os, pathlib, sys, time
import urllib.request

API = "http://localhost:8000/chat"


def call(question, ablation):
    body = json.dumps({"user_id": "eval", "question": question, "ablation": ablation}).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def cited_ids(resp):
    return [c.get("source_id") for c in resp.get("claims", [])]


def lookup_source_systems(ids, dsn):
    """{source_id: system_id} for doc chunks and heuristics. Unknown ids are absent."""
    import psycopg
    ids = sorted(set(i for i in ids if i))
    if not ids:
        return {}
    with psycopg.connect(dsn) as con:
        rows = con.execute(
            "SELECT id, system_id FROM doc_chunk WHERE id = ANY(%s)"
            " UNION ALL SELECT id, system_id FROM heuristic WHERE id = ANY(%s)",
            (ids, ids)).fetchall()
    return dict(rows)


def contaminated(item, resp, source_systems):
    """True if an answer cites any source outside the gold system; None if not applicable.

    source_systems=None means the DB lookup was unavailable -> can't score (None).
    """
    if item.get("system") is None or resp.get("type") != "answer" or source_systems is None:
        return None
    return any(source_systems.get(s) != item["system"] for s in cited_ids(resp))


def score(item, resp, source_systems):
    expect, got = item["expect"], resp.get("type")
    cited = cited_ids(resp)
    ctx = resp.get("context") or {}
    gold = set(item.get("gold_nodes") or [])
    claims = resp.get("claims", [])
    return {
        "id": item["id"],
        "category": item["category"],
        "expect": expect,
        "got": got,
        "behaviour_ok": got == expect,
        # clarify items have no gold context; answer/refer must resolve the gold system+version
        "context_ok": None if item["system"] is None else (ctx.get("system") == item["system"]
                                                           and ctx.get("version") == item["version"]),
        "retrieval_hit": bool(gold & set(cited)) if gold else None,
        "contaminated": contaminated(item, resp, source_systems),
        "false_refusal": expect == "answer" and got == "refer",
        "correct_refusal": expect == "refer" and got == "refer",
        "expert_ok": (item.get("expert") is None) or any(
            e.get("id") == item["expert"] for e in resp.get("experts", [])),
        "n_claims": len(claims),
        "dropped_claims": resp.get("dropped_claims", 0),
        "error": resp.get("error", ""),
    }


def rate(rows, key, subset=None):
    xs = [r[key] for r in rows if (subset is None or subset(r)) and r[key] is not None]
    if not xs:
        return "n/a (0 items)"
    return f"{sum(xs)}/{len(xs)} ({100*sum(xs)/len(xs):.0f}%)"


def load_items(path):
    p = pathlib.Path(path)
    if not p.exists():
        sys.exit(f"golden set not found: {p} (copy eval/golden_template.jsonl to start)")
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", default="eval/golden.jsonl")
    ap.add_argument("--config", type=int, default=4)
    a = ap.parse_args()

    items = load_items(a.golden)
    if not items:
        print(f"no items in {a.golden}; nothing to evaluate")
        return

    results = []
    for it in items:
        t0 = time.time()
        try:
            resp = call(it["q"], a.config)
        except Exception as e:  # keep going; record failure
            resp = {"type": "error", "error": str(e)}
        results.append((it, resp, round(time.time() - t0, 2)))

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    source_systems = None
    try:
        source_systems = lookup_source_systems(
            [s for _, resp, _ in results for s in cited_ids(resp)], os.environ["DATABASE_URL"])
    except Exception as e:
        print(f"WARNING: source lookup failed, contamination not scored: {e}")

    rows = []
    for it, resp, latency in results:
        r = score(it, resp, source_systems)
        r["latency_s"] = latency
        rows.append(r)

    out = pathlib.Path("eval/results"); out.mkdir(parents=True, exist_ok=True)
    f = out / f"results_config{a.config}_{int(time.time())}.csv"
    with f.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)

    traps = lambda r: r["category"] == "context_trap"
    errors = sum(1 for r in rows if r["got"] == "error")
    total_claims = sum(r["n_claims"] + r["dropped_claims"] for r in rows)
    dropped = sum(r["dropped_claims"] for r in rows)
    print(f"config={a.config}  items={len(rows)}  errors={errors}  -> {f}")
    if errors == len(rows):
        print("WARNING: every call failed; is the API running on :8000?")
    print("behaviour acc     ", rate(rows, "behaviour_ok"))
    print("context acc       ", rate(rows, "context_ok"))
    print("retrieval hit     ", rate(rows, "retrieval_hit"))
    print("contamination     ", rate(rows, "contaminated", traps), " <- headline (traps)")
    print("contamination all ", rate(rows, "contaminated"))
    print("correct refusals  ", rate(rows, "correct_refusal", lambda r: r["expect"] == "refer"))
    print("false refusals    ", rate(rows, "false_refusal", lambda r: r["expect"] == "answer"))
    print("expert routing    ", rate(rows, "expert_ok"))
    print(f"unsupported claims {dropped}/{total_claims}")


if __name__ == "__main__":
    main()
