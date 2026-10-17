"""Golden-set eval harness.

Usage:
  python eval/run_eval.py                      # full pipeline, eval/golden.jsonl
  python eval/run_eval.py --config 1           # ablation: 1=plain RAG ... 4=full
  python eval/run_eval.py --golden eval/golden_template.jsonl

Expects the API at http://localhost:8000 (override with EVAL_API_BASE; see docs/API_CONTRACT.md).
/chat accepts an optional "ablation" int for configs 1-4. Items may carry a "node" ("node:PROD" /
"node:DR"); it is sent via POST /session before the item so the session node is honoured.

Optional golden fields (see eval/README.md): must_include (list of strings or any-of lists),
must_not_include, forbidden_sources (ids, fnmatch globs ok), both_sides (list of any-of id groups).
Every rate is printed with n and a 95% Wilson confidence interval.

Contamination is computed from the DB, not from the API's own claims: every cited
source_id is looked up in doc_chunk/heuristic (DATABASE_URL) and compared with the
item's gold system. A citation whose source isn't in the DB counts as contaminated.
"""
import argparse, csv, fnmatch, json, math, os, pathlib, re, sys, time
import urllib.error, urllib.request

BASE = os.environ.get("EVAL_API_BASE", "http://localhost:8000").rstrip("/")
API = BASE + "/chat"
SESSION = BASE + "/session"


def call(question, ablation):
    body = json.dumps({"user_id": "eval", "question": question, "ablation": ablation}).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def set_node(node):
    """Switch the API session to `node` (POST /session) so context comes from the session."""
    body = json.dumps({"node": node}).encode()
    req = urllib.request.Request(SESSION, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def api_up():
    """False only when the API can't be reached at all (an HTTP error still means it is up)."""
    try:
        urllib.request.urlopen(SESSION, timeout=5).read()
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False
    return True


def cited_ids(resp):
    """Claim citations (classic mode) plus reply citations (assistant mode)."""
    return [c.get("source_id") for c in resp.get("claims", [])] + list((resp.get("reply_citations") or {}).values())


def effective_type(resp):
    """Assistant mode always returns type 'answer' and declines in words. For scoring, an answer with no citations
    counts as a clarify if it ends with a question, otherwise as a refer."""
    t = resp.get("type")
    if t == "answer" and resp.get("reply") is not None and not cited_ids(resp):
        return "clarify" if resp["reply"].strip().endswith("?") else "refer"
    return t


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


def wilson(k, n, z=1.96):
    """95% Wilson score interval (lo, hi) for k successes of n; (None, None) if n == 0."""
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def _norm(t):
    return re.sub(r"\s+", " ", (t or "").replace("’", "'").lower())


def claims_text(resp):
    return _norm(" ".join([c.get("text", "") for c in resp.get("claims", [])] + [resp.get("reply") or ""]))


def includes_all(groups, text):
    """Every group must match; a group is a phrase or a list of alternatives (any-of). Case-insensitive."""
    text = _norm(text)
    return all(any(_norm(a) in text for a in ([g] if isinstance(g, str) else g)) for g in groups)


def includes_any(phrases, text):
    text = _norm(text)
    return any(_norm(p) in text for p in phrases)


def forbidden_hits(patterns, cited):
    """Cited ids matching any forbidden id or fnmatch glob (e.g. 'maria:*')."""
    return [c for c in cited if c and any(fnmatch.fnmatchcase(c, p) for p in patterns)]


def both_sides_ok(groups, cited):
    """Each group (any-of source ids) must have at least one citation."""
    return all(any(g in set(cited) for g in grp) for grp in groups)


def contaminated(item, resp, source_systems):
    """True if an answer cites any source outside the gold system; None if not applicable.

    source_systems=None means the DB lookup was unavailable -> can't score (None).
    """
    if item.get("system") is None or resp.get("type") != "answer" or source_systems is None:
        return None
    return any(source_systems.get(s) != item["system"] for s in cited_ids(resp))


def score(item, resp, source_systems):
    expect, got = item["expect"], effective_type(resp)
    cited = cited_ids(resp)
    ctx = resp.get("context") or {}
    gold = set(item.get("gold_nodes") or [])
    claims = resp.get("claims", [])
    is_answer = got == "answer"
    text = claims_text(resp)
    must = item.get("must_include") or []
    must_not = item.get("must_not_include") or []
    forb = item.get("forbidden_sources") or []
    both = item.get("both_sides") or []
    node_bad = bool(item.get("node") and ctx.get("site") and ctx.get("site") != item["node"])
    return {
        "id": item["id"],
        "category": item["category"],
        "expect": expect,
        "got": got,
        "behaviour_ok": got == expect,
        # clarify items have no gold context; answer/refer must resolve the gold system+version
        "context_ok": None if item["system"] is None else (ctx.get("system") == item["system"]
                                                           and ctx.get("version") == item.get("version")
                                                           and not node_bad),
        "retrieval_hit": bool(gold & set(cited)) if gold else None,
        "contaminated": contaminated(item, resp, source_systems),
        "false_refusal": expect == "answer" and got == "refer",
        "correct_refusal": expect == "refer" and got == "refer",
        "expert_ok": (item.get("expert") is None) or any(
            e.get("id") == item["expert"] for e in resp.get("experts", []))
            or any((c or "").startswith(item["expert"] + ":") for c in cited),
        # only meaningful for answers; a wrong behaviour on an answer item fails it
        "must_include_ok": (is_answer and includes_all(must, text)) if (must and expect == "answer") else None,
        "must_not_ok": (not includes_any(must_not, text)) if (must_not and is_answer) else None,
        "forbidden_clean": (not forbidden_hits(forb, cited)) if (forb and is_answer) else None,
        "both_sides_ok": (is_answer and both_sides_ok(both, cited)) if both else None,
        "n_claims": len(claims),
        "dropped_claims": resp.get("dropped_claims", 0),
        "error": resp.get("error", ""),
    }


def rate(rows, key, subset=None):
    xs = [r[key] for r in rows if (subset is None or subset(r)) and r[key] is not None]
    if not xs:
        return "n/a (0 items)"
    k, n = sum(xs), len(xs)
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({100*k/n:.0f}%) 95% CI [{100*lo:.0f}-{100*hi:.0f}%] n={n}"


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

    if not api_up():
        sys.exit(f"API not reachable at {BASE}: start the backend (see docs/API_CONTRACT.md) "
                 "or set EVAL_API_BASE. Nothing was evaluated.")

    results = []
    node = None
    for it in items:
        t0 = time.time()
        try:
            if it.get("node") and it["node"] != node:
                set_node(it["node"])
                node = it["node"]
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
    print("must_include      ", rate(rows, "must_include_ok"))
    print("must_not_include  ", rate(rows, "must_not_ok"), " (ok = no banned phrase)")
    print("forbidden clean   ", rate(rows, "forbidden_clean"), " (ok = no forbidden source cited)")
    print("both sides (conflict)", rate(rows, "both_sides_ok"))
    for cat in sorted({r["category"] for r in rows}):
        print(f"  behaviour[{cat}]".ljust(20), rate(rows, "behaviour_ok", lambda r, c=cat: r["category"] == c))
    print(f"unsupported claims {dropped}/{total_claims}")


if __name__ == "__main__":
    main()
