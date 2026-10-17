"""Demo learning history for the emerging veterans (fictional juniors in kg/seed/persons.yaml, level 'emerging').

    python -m backend.graph.demo_learning

Gives each one a few questions in their 1-2 subsystems, logged like real /chat answers (citations = a veteran note and
manual sections linked to that subsystem in the graph), plus a self-reported starting level, so their Learning maps
are not empty in the demo. Idempotent: replaces only these users' answer_log and self_level rows. Synthetic data.
"""
import json
import random
import sys
from datetime import datetime, timedelta, timezone

from backend.pipeline.answer import _rows, connect

QUESTIONS = {
    "sub:TMF": ["why is the TMF audit trail filling up?", "what does TMF 185 mean?", "how do I find the oldest transaction?",
                "what does STATUS AUDITTRAIL show?"],
    "sub:PATHWAY": ["what does Pathway 1034 no server available mean?", "how do I check a server class?",
                    "a server class shows FROZEN, what now?"],
    "sub:SCF-STORAGE": ["what does SCF STATUS DISK show?", "the mirror revive looks stuck, what do I check?",
                        "what is DISK 5032?"],
    "sub:PEEK": ["how do I check CPU busy with PEEK?", "what happens after a CPU takeover?"],
    "sub:MEASURE": ["what does CPU-BUSY-TIME mean in Measure?", "how do I read a Measure CPU report?"],
    "sub:TACL": ["how do I see what a process is running in TACL?", "why does my macro behave differently on DR?"],
    "sub:FUP": ["who has this file open?", "how do I use FUP LISTOPENS?"],
}


def history(user, subs, rng, sources, now):
    """[(ts, question, system, citations)] for one junior: 2-4 questions per subsystem, newest last."""
    out = []
    for sub in subs:
        qs = QUESTIONS[sub][:]
        rng.shuffle(qs)
        for q in qs[:rng.randint(2, min(4, len(qs)))]:
            notes, docs = sources[sub]
            cites = (rng.sample(notes, 1) if notes and rng.random() < 0.7 else []) + rng.sample(docs, min(2, len(docs)))
            out.append((now - timedelta(days=rng.randint(1, 14), hours=rng.randint(0, 9)), q, sub, cites))
    return sorted(out)


def main():
    rng, now = random.Random(31), datetime.now(timezone.utc)
    with connect() as conn:
        juniors = _rows(conn, "SELECT p.id, array_agg(e.dst ORDER BY e.weight DESC, e.dst) AS subs, max(e.weight) AS w "
                              "FROM person p JOIN edge e ON e.src = p.id AND e.rel = 'expert_in' "
                              "WHERE p.level = 'emerging' GROUP BY p.id ORDER BY p.id")
        all_subs = [r["id"] for r in _rows(conn, "SELECT id FROM entity WHERE kind = 'system'")]
        sources = {}
        for sub in all_subs:
            notes = [r["id"] for r in _rows(conn, "SELECT id FROM heuristic WHERE system_id = %s AND status = 'approved' "
                                                  "AND (site_id = 'node:PROD' OR site_id IS NULL) ORDER BY id", (sub,))]
            docs = [r["src"] for r in _rows(conn, "SELECT DISTINCT e.src FROM edge e JOIN entity x ON x.id = e.dst "
                                                  "WHERE e.rel = 'about' AND e.src LIKE 'doc:%%' AND x.parent_id = %s "
                                                  "ORDER BY e.src LIMIT 40", (sub,))]
            sources[sub] = (notes, docs)
        ids = [j["id"] for j in juniors]
        conn.execute("DELETE FROM answer_log WHERE user_id = ANY(%s)", (ids,))
        conn.execute("DELETE FROM self_level WHERE user_id = ANY(%s)", (ids,))
        n = 0
        for j in juniors:
            for ts, q, sub, cites in history(j["id"], j["subs"], rng, sources, now):
                conn.execute("INSERT INTO answer_log (ts, user_id, question, context, outcome, citations) VALUES (%s,%s,%s,%s,'answer',%s)",
                             (ts, j["id"], q, json.dumps({"system": sub, "version": "rvu:L", "site": "node:PROD"}), cites))
                n += 1
            for sub in all_subs:  # starting level they gave themselves: some in their own area, new elsewhere
                conn.execute("INSERT INTO self_level (user_id, system_id, level) VALUES (%s,%s,%s)",
                             (j["id"], sub, "some" if sub in j["subs"] else "new"))
        conn.commit()
    print(f"{len(juniors)} emerging veterans, {n} logged questions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
