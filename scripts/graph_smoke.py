"""DB smoke check for the knowledge graph (needs Docker Postgres + `python -m backend.graph.load`).

    python scripts/graph_smoke.py ["why is the audit trail filling?"]

Prints resolved entities, notes, commands, experts and the walked path for \\PROD and \\DR.
"""
import sys

import psycopg

from backend import settings
from backend.graph.query import lookup, resolve

Q = "why is the audit trail filling?"
CONTEXTS = {"\\PROD": {"system": "sub:TMF", "version": "rvu:L", "site": "node:PROD"},
            "\\DR": {"system": "sub:TMF", "version": "rvu:L", "site": "node:DR"}}


def show(conn, question, label, ctx):
    r = resolve(conn, question, ctx)
    print(f"\n===== {label}  ctx={ctx['site']}/{ctx['version']}/{ctx['system']}")
    print("subsystem:", r["subsystem"], "| nodes_mentioned:", r["nodes_mentioned"])
    print("entities:", [f"{e['id']} ({e['matched']})" for e in r["entities"]])
    ctx = {**ctx, "system": ctx["system"] or r["subsystem"]}
    res = lookup(conn, [e["id"] for e in r["entities"]], ctx)
    print("heuristics:")
    for h in res["heuristics"]:
        print(f"  {h['id']:10} {h['owner_name']:14} [{h['scope']}] {h['relation']}")
    print("doc_chunks:", [d["id"] for d in res["doc_chunks"]])
    print("  edition of first:", res["doc_chunks"][0]["edition"] if res["doc_chunks"] else None)
    print("commands:", [f"{c['command']} ({c['risk']})" for c in res["commands"]])
    print("experts:", [f"{x['name']} {x['availability']} - {x['reason']}" for x in res["experts"]])
    print(f"path ({len(res['path'])} edges):")
    for e in res["path"]:
        print(f"  {e['src']} -{e['rel']}-> {e['dst']}   [{e['source_id']}]")
    return res


def main():
    q = sys.argv[1] if len(sys.argv) > 1 else Q
    with psycopg.connect(settings.DATABASE_URL) as conn:
        out = {label: show(conn, q, label, ctx) for label, ctx in CONTEXTS.items()}
    prod_ids = {h["id"] for h in out["\\PROD"]["heuristics"]}
    dr_ids = {h["id"] for h in out["\\DR"]["heuristics"]}
    print("\nPROD-only notes:", sorted(prod_ids - dr_ids), "| DR-only notes:", sorted(dr_ids - prod_ids))
    assert not any(h["scope"].startswith("\\PROD") for h in out["\\DR"]["heuristics"]), "PROD note leaked into DR"
    print("OK: no \\PROD-scoped note returned for \\DR")


if __name__ == "__main__":
    main()
