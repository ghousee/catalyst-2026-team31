"""Golden-set eval harness (skeleton).

Usage:
  python eval/run_eval.py                      # full pipeline, eval/golden.jsonl
  python eval/run_eval.py --config 1           # ablation: 1=plain RAG ... 4=full
  python eval/run_eval.py --golden eval/golden_template.jsonl

Expects the API at http://localhost:8000/chat (see docs/API_CONTRACT.md).
The /chat endpoint should accept an optional "ablation" int for configs 1-4.
"""
import argparse, csv, json, pathlib, time
import urllib.request

API = "http://localhost:8000/chat"


def call(question, ablation):
    body = json.dumps({"user_id": "eval", "question": question, "ablation": ablation}).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def score(item, resp):
    expect, got = item["expect"], resp.get("type")
    cited = [c["source_id"] for c in resp.get("claims", [])]
    ctx = resp.get("context") or {}
    gold = set(item.get("gold_nodes") or [])
    claims = resp.get("claims", [])
    return {
        "id": item["id"],
        "category": item["category"],
        "expect": expect,
        "got": got,
        "behaviour_ok": got == expect,
        "context_ok": (item["system"] is None) or (ctx.get("system") == item["system"]
                                                    and ctx.get("version") == item["version"]),
        "retrieval_hit": bool(gold & set(cited)) if gold else None,
        # contamination: any citation tied to a different system than gold (heuristic: id prefix check is
        # project-specific; replace with a lookup of each source's system_id)
        "contaminated": (item["category"] == "context_trap" and got == "answer"
                         and not (gold & set(cited))),
        "false_refusal": expect == "answer" and got == "refer",
        "correct_refusal": expect == "refer" and got == "refer",
        "expert_ok": (item.get("expert") is None) or any(
            e.get("id") == item["expert"] for e in resp.get("experts", [])),
        "n_claims": len(claims),
        "dropped_claims": resp.get("dropped_claims", 0),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", default="eval/golden.jsonl")
    ap.add_argument("--config", type=int, default=4)
    a = ap.parse_args()

    items = [json.loads(l) for l in pathlib.Path(a.golden).read_text().splitlines() if l.strip()]
    rows = []
    for it in items:
        t0 = time.time()
        try:
            resp = call(it["q"], a.config)
        except Exception as e:  # keep going; record failure
            resp = {"type": "error", "error": str(e)}
        r = score(it, resp)
        r["latency_s"] = round(time.time() - t0, 2)
        rows.append(r)

    out = pathlib.Path("eval/results"); out.mkdir(parents=True, exist_ok=True)
    f = out / f"results_config{a.config}_{int(time.time())}.csv"
    with f.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)

    def rate(key, subset=None):
        xs = [r[key] for r in rows if (subset is None or subset(r)) and r[key] is not None]
        return f"{sum(xs)}/{len(xs)} ({100*sum(xs)/max(len(xs),1):.0f}%)"

    traps = lambda r: r["category"] == "context_trap"
    total_claims = sum(r["n_claims"] + r["dropped_claims"] for r in rows)
    dropped = sum(r["dropped_claims"] for r in rows)
    print(f"config={a.config}  items={len(rows)}  -> {f}")
    print("behaviour acc     ", rate("behaviour_ok"))
    print("context acc       ", rate("context_ok"))
    print("retrieval hit     ", rate("retrieval_hit"))
    print("contamination     ", rate("contaminated", traps), " <- headline")
    print("correct refusals  ", rate("correct_refusal", lambda r: r["expect"] == "refer"))
    print("false refusals    ", rate("false_refusal", lambda r: r["expect"] == "answer"))
    print("expert routing    ", rate("expert_ok"))
    print(f"unsupported claims {dropped}/{total_claims}")


if __name__ == "__main__":
    main()
