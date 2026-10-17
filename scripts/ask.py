"""Ask the pipeline directly (no server): python scripts/ask.py "why is the audit trail filling?" [--node PROD|DR]"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from backend.pipeline.answer import answer, warm  # noqa: E402

ICON = {"doc": "[doc]", "veteran": "[vet]"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--node", default="PROD", choices=["PROD", "DR"])
    a = ap.parse_args()
    warm()
    res = answer(a.question, {"node": f"node:{a.node}", "series": "rvu:L", "user": "cli"})
    d = res.get("debug", {})
    print(f"TYPE: {res['type']}")
    if res.get("context"):
        c = res["context"]
        print(f"context: {c['display']}  ({c['system']}, {c['version']}, {c['site']}) confidence {c['confidence']}")
    if res["type"] == "clarify":
        print(res["question"])
        for o in res["options"]:
            print(f"  - {o['label']} -> {o['value']}")
        return
    print("\ngraph entities:", ", ".join(f"{e['id']} ({e['matched']})" for e in d.get("entities", [])) or "-")
    for e in d.get("path", [])[:8]:
        print(f"  {e['src']} -{e['rel']}-> {e['dst']}")
    if len(d.get("path", [])) > 8:
        print(f"  ... {len(d['path']) - 8} more edges")
    print("\nretrieved sources:")
    for s in d.get("retrieved", []):
        print(f"  {ICON[s['lane']]} {s['id']}  {s.get('owner') or s.get('edition') or ''}")
    g = d.get("gate") or res["quality"]["gate"]
    print(f"\ngate: {'sufficient' if g['sufficient'] else 'INSUFFICIENT'} - {g['reason']}")
    if res["type"] == "refer":
        print("REFER:", res["reason"])
    else:
        print("\nclaims:")
        for c in res["claims"]:
            print(f"  {ICON[c['lane']]} {c['text']}\n        cite {c['source_id']}  minicheck {c['score']:.2f}")
        for x in d.get("dropped", []):
            print(f"  [DROPPED:{x['why']}] {x['text']}\n        cite {x['source_id']}  minicheck {x['score']}")
        print("\nsource cards:")
        for s in res["sources"]:
            print(f"  {s['id']}  " + (f"{s['title']} | {s['applies_to']}" if s["kind"] == "doc"
                                      else f"{s['owner_name']}, {s['owner_role']}, {s['years']}y | {s['captured_via']} {s['captured_at']} | {s['scope']} | {s.get('relation', '')}"))
    print("\nexperts:")
    for e in res["experts"]:
        print(f"  {e['name']} ({e.get('availability')}) - {e['reason']}")
    q = res["quality"]
    print(f"\nquality: {q['claims_verified']}/{q['claims_total']} verified ({q['dropped']} dropped), support avg {q['support_avg']:.2f} "
          f"min {q['support_min']:.2f}, context {q['context_confidence']} ({q['context_source']}), lanes {q['sources_by_lane']}")
    print(f"timings ms: {q['stages_ms']}  total {q['latency_ms']}")


if __name__ == "__main__":
    main()
