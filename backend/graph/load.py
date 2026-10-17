"""Load kg/seed/*.yaml into entity / person / heuristic / edge (idempotent upsert).

    python -m backend.graph.load [--no-embed] [--cpu]

Fails loudly (exit 1, nothing committed) if any edge.source_id, command source_id, edge endpoint or heuristic
relation target does not exist in doc_chunk / heuristic / entity / person. Seed edges are owned by
created_by = 'seed': they are deleted and re-inserted on every run, so removing a line from the YAML removes the edge.
"""
import argparse
import sys
from pathlib import Path

import psycopg
import yaml
from psycopg.types.json import Json

from backend import settings
from backend.ingest import embedder

SEED = Path(__file__).resolve().parents[2] / "kg" / "seed"
HEURISTIC_REL_FIELDS = ("about", "mentions", "extends", "contradicts", "disagrees_with")


def read_seed(seed_dir=SEED):
    def y(name):
        return yaml.safe_load((seed_dir / name).read_text(encoding="utf-8"))
    return y("entities.yaml")["entities"], y("persons.yaml")["persons"], y("heuristics.yaml")["heuristics"], y("edges.yaml")["edges"]


def heuristic_edges(heuristics):
    """(src, rel, dst, source_id, weight) generated from each heuristic's relation fields and scope."""
    out = []
    for h in heuristics:
        out.append((h["id"], "about", h["system"], h["id"], 1.0))
        for scope in ("version", "site"):
            if h[scope] != "all":
                out.append((h["id"], "applies_to", h[scope], h["id"], 1.0))
        for rel in HEURISTIC_REL_FIELDS:
            for dst in h.get(rel) or []:
                out.append((h["id"], rel, dst, h["id"], 1.0))
    return out


def seed_edges(raw_edges):
    return [(e[0], e[1], e[2], e[3], float(e[4]) if len(e) > 4 else 1.0) for e in raw_edges]


def validate(entities, persons, heuristics, edges, known_chunks, known_entities):
    """Return a list of problem strings (empty = OK). Pure: takes the id sets, no DB."""
    problems = []
    ent_ids = set(known_entities) | {e["id"] for e in entities}
    person_ids = {p["id"] for p in persons}
    heur_ids = {h["id"] for h in heuristics}
    cite_ok = set(known_chunks) | heur_ids
    node_ok = ent_ids | person_ids | heur_ids | set(known_chunks)
    for e in entities:
        if e["kind"] == "command":
            sid = (e.get("props") or {}).get("source_id")
            if sid not in cite_ok:
                problems.append(f"command {e['id']}: source_id {sid!r} not in doc_chunk/heuristic")
        if e.get("parent_id") and e["parent_id"] not in ent_ids:
            problems.append(f"entity {e['id']}: unknown parent {e['parent_id']!r}")
    for h in heuristics:
        for k in ("owner", "signed_by"):
            if h.get(k) and h[k] not in person_ids:
                problems.append(f"heuristic {h['id']}: unknown {k} {h[k]!r}")
        for f in ("system", "version", "site"):
            if h[f] != "all" and h[f] not in ent_ids:
                problems.append(f"heuristic {h['id']}: unknown {f} {h[f]!r}")
        if h["status"] == "approved" and not h.get("signed_by"):
            problems.append(f"heuristic {h['id']}: approved but unsigned")
    for src, rel, dst, sid, _ in edges:
        if sid not in cite_ok:
            problems.append(f"edge {src} -{rel}-> {dst}: source_id {sid!r} not in doc_chunk/heuristic")
        for end in (src, dst):
            if end not in node_ok:
                problems.append(f"edge {src} -{rel}-> {dst}: unknown endpoint {end!r}")
    return problems


def upsert(conn, entities, persons, heuristics, edges, embed=True, cpu=False):
    with conn.cursor() as cur:
        for e in entities:
            if e.get("alias_only"):
                cur.execute("UPDATE entity SET aliases = %s WHERE id = %s", (e["aliases"], e["id"]))
                if cur.rowcount != 1:
                    raise SystemExit(f"alias_only entity {e['id']} missing from DB (run the manual loader first)")
            else:
                cur.execute(
                    """INSERT INTO entity (id, kind, name, aliases, parent_id, props) VALUES (%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (id) DO UPDATE SET kind=EXCLUDED.kind, name=EXCLUDED.name,
                         aliases=EXCLUDED.aliases, parent_id=EXCLUDED.parent_id, props=EXCLUDED.props""",
                    (e["id"], e["kind"], e["name"], e["aliases"], e.get("parent_id"), Json(e.get("props") or {})))
        for p in persons:
            cur.execute(
                """INSERT INTO person (id, name, role, team, years, expertise, availability, active, contact)
                   VALUES (%(id)s,%(name)s,%(role)s,%(team)s,%(years)s,%(expertise)s,%(availability)s,%(active)s,%(contact)s)
                   ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, role=EXCLUDED.role, team=EXCLUDED.team,
                     years=EXCLUDED.years, expertise=EXCLUDED.expertise, availability=EXCLUDED.availability,
                     active=EXCLUDED.active, contact=EXCLUDED.contact""", p)
        vecs = [None] * len(heuristics)
        if embed:
            vecs, _ = embedder.embed([embedder.doc_text(h["trigger"][:80], f"{h['trigger']} {h['call']} {h['why']}")
                                      for h in heuristics], cpu=cpu)
        for h, v in zip(heuristics, vecs):
            vid = None if h["version"] == "all" else h["version"]
            sid = None if h["site"] == "all" else h["site"]
            cur.execute(
                """INSERT INTO heuristic (id, owner_id, trigger_text, call_text, why_text, not_when_text, system_id,
                     version_id, site_id, all_versions, all_sites, provenance, status, endorsements, last_validated,
                     is_trigger, kind, pattern, captured_via, captured_at, signed_by, signed_at, embedding)
                   VALUES (%(id)s,%(owner)s,%(trigger)s,%(call)s,%(why)s,%(not_when)s,%(system)s,%(vid)s,%(sid)s,%(av)s,%(as_)s,
                     %(provenance)s,%(status)s,%(endorsements)s,%(last_validated)s,%(is_trigger)s,%(kind)s,%(pattern)s,
                     %(captured_via)s,%(captured_at)s,%(signed_by)s,%(signed_at)s,%(emb)s::vector)
                   ON CONFLICT (id) DO UPDATE SET owner_id=EXCLUDED.owner_id, trigger_text=EXCLUDED.trigger_text,
                     call_text=EXCLUDED.call_text, why_text=EXCLUDED.why_text, not_when_text=EXCLUDED.not_when_text,
                     system_id=EXCLUDED.system_id, version_id=EXCLUDED.version_id, site_id=EXCLUDED.site_id,
                     all_versions=EXCLUDED.all_versions, all_sites=EXCLUDED.all_sites, provenance=EXCLUDED.provenance,
                     status=EXCLUDED.status, endorsements=EXCLUDED.endorsements, last_validated=EXCLUDED.last_validated,
                     is_trigger=EXCLUDED.is_trigger, kind=EXCLUDED.kind, pattern=EXCLUDED.pattern,
                     captured_via=EXCLUDED.captured_via, captured_at=EXCLUDED.captured_at, signed_by=EXCLUDED.signed_by,
                     signed_at=EXCLUDED.signed_at, embedding=COALESCE(EXCLUDED.embedding, heuristic.embedding)""",
                {**h, "vid": vid, "sid": sid, "av": vid is None, "as_": sid is None,
                 "is_trigger": h.get("is_trigger", False), "not_when": h.get("not_when"),
                 "pattern": Json(h["pattern"]) if h.get("pattern") else None,
                 "last_validated": h.get("last_validated"), "signed_by": h.get("signed_by"), "signed_at": h.get("signed_at"),
                 "emb": None if v is None else "[" + ",".join(map(str, v)) + "]"})
        cur.execute("DELETE FROM edge WHERE created_by = 'seed'")
        for src, rel, dst, sid, w in edges:
            cur.execute("""INSERT INTO edge (src, rel, dst, weight, source_id, created_by) VALUES (%s,%s,%s,%s,%s,'seed')
                           ON CONFLICT (src, rel, dst) DO UPDATE SET weight=EXCLUDED.weight, source_id=EXCLUDED.source_id,
                             created_by='seed'""", (src, rel, dst, w, sid))


def counts(conn):
    def q(s):
        return conn.execute(s).fetchall()
    return {"entities_by_kind": dict(q("SELECT kind, count(*) FROM entity GROUP BY kind ORDER BY kind")),
            "edges_by_rel": dict(q("SELECT rel, count(*) FROM edge GROUP BY rel ORDER BY rel")),
            "persons": q("SELECT count(*) FROM person")[0][0],
            "heuristics_by_status": dict(q("SELECT status, count(*) FROM heuristic GROUP BY status"))}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-embed", action="store_true")
    ap.add_argument("--cpu", action="store_true")
    a = ap.parse_args(argv)
    entities, persons, heuristics, raw = read_seed()
    edges = seed_edges(raw) + heuristic_edges(heuristics)
    with psycopg.connect(settings.DATABASE_URL) as conn:
        chunks = {r[0] for r in conn.execute("SELECT id FROM doc_chunk")}
        known = {r[0] for r in conn.execute("SELECT id FROM entity")}
        problems = validate(entities, persons, heuristics, edges, chunks, known)
        if problems:
            print("SEED VALIDATION FAILED:\n  " + "\n  ".join(problems), file=sys.stderr)
            return 1
        upsert(conn, entities, persons, heuristics, edges, embed=not a.no_embed, cpu=a.cpu)
        conn.commit()
        print(counts(conn))
    return 0


if __name__ == "__main__":
    sys.exit(main())
