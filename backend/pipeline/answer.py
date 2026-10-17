"""The whole chat pipeline in one function: answer(question, session, override) -> one /chat contract shape.

resolve context -> graph lookup + hybrid search -> sufficiency gate -> Qwen claims -> MiniCheck per claim -> answer card.
Never guesses the context: unresolved subsystem / node mismatch -> `clarify`; insufficient or unverifiable -> `refer`.
"""
import json
import os
import re
import time
from itertools import zip_longest

import psycopg
from pgvector.psycopg import register_vector

from backend import settings
from backend.graph.query import SHORT, _captured, lookup, resolve, scope_text
from backend.ingest.embedder import embed_query
from backend.pipeline import gate, generate, verify
from backend.pipeline.retrieve import hybrid_search

VERIFY_THRESHOLD = float(os.getenv("VERIFY_THRESHOLD", "0.5"))
GEN_CHARS = 1800   # per-source text handed to Qwen (MiniCheck sees the full text)
MAX_DOCS = 6
MAX_CLAIMS = 4     # fewer claims = faster generation + verification
MAX_NOTES = 3      # veteran notes per answer (lookup returns them most-relevant first)
SPECIFIC = {"event", "object", "command", "metric"}  # entity kinds that pin a question down

# the manual as the speaker ("the manual recommends X", "according to the documentation"); a veteran saying
# "don't rely on the manual's X" is legitimate (that is the contradicts-the-manual feature) and must pass
_MANUAL_SPEAKS = re.compile(
    r"\b(?:the\s+)?(?:manual|documentation|docs|reference(?:\s+guide)?)\s+(?:says|states|recommends|requires|advises|"
    r"suggests|instructs|specifies)\b|\baccording\s+to\s+the\s+(?:manual|documentation|docs|reference)\b", re.I)


def misattributed(text, lane, owner_names=()):
    """True if a claim speaks for the wrong kind of source: a veteran note quoted as 'the manual says',
    or a manual section quoted as a named veteran. MiniCheck misses this (it scored such a claim 0.97)."""
    if lane == "veteran":
        return bool(_MANUAL_SPEAKS.search(text))
    return any(n and n.split()[0].lower() in text.lower() for n in owner_names)


def _clean(text):
    """Qwen sometimes renders the node backslash as a stray non-ASCII character (Cyrillic, a symbol) before
    PROD/DR; restore it."""
    text = re.sub(r"[^\x00-\x7f](?=PROD\b|DR\b)", lambda m: "\\", text)
    return re.sub(r"\\{2,}(?=PROD|DR)", lambda m: "\\", text)  # doubled backslash from JSON escaping


def connect():
    conn = psycopg.connect(settings.DATABASE_URL)
    register_vector(conn)
    return conn


def warm():
    """Load MiniCheck once (lazy singleton) and get Qwen + the embedder into memory, so the first question isn't slow."""
    verify._load()
    embed_query("warm up")
    from backend.pipeline import llm
    llm.chat([{"role": "user", "content": "ok"}], max_tokens=1)


def _rows(conn, sql, params=()):
    cur = conn.execute(sql, params)
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# ---------------------------------------------------------------- source cards (answers and GET /sources/{id})
def source_card(conn, sid):
    """Doc or heuristic card with the v2 fields, or None if the id is unknown."""
    if sid.startswith("doc:"):
        rows = _rows(conn, "SELECT id, section, text, edition, doc_version FROM doc_chunk WHERE id = %s", (sid,))
        if not rows:
            return None
        d = rows[0]
        edition = d["edition"] or ""
        return {"id": d["id"], "kind": "doc", "title": edition.split(",")[0] or d["section"] or d["id"],
                "part_number": d["doc_version"], "section": d["section"], "applies_to": edition,
                "snippet": d["text"][:300]}
    rows = _rows(conn, "SELECT h.*, p.name AS owner_name, p.role AS owner_role, p.years AS years "
                       "FROM heuristic h JOIN person p ON p.id = h.owner_id WHERE h.id = %s", (sid,))
    if not rows:
        return None
    h = rows[0]
    rel = _rows(conn, "SELECT rel, dst FROM edge WHERE src = %s AND rel IN ('contradicts', 'extends')", (sid,))
    rel = sorted(rel, key=lambda e: e["rel"] != "contradicts")  # contradicts wins over extends
    card = {"id": h["id"], "kind": "heuristic", "owner": h["owner_id"], "owner_name": h["owner_name"],
            "owner_role": h["owner_role"], "years": h["years"], "captured_via": _captured(h),
            "captured_at": str(h["captured_at"] or ""), "endorsements": h["endorsements"],
            "last_validated": str(h["last_validated"] or ""), "scope": scope_text(h), "why": h["why_text"] or ""}
    if rel:
        card["relation"] = f"{rel[0]['rel']}:{rel[0]['dst']}"
    return card


# ---------------------------------------------------------------- small helpers
def _ms(stages, name, t0):
    stages[name] = round((time.perf_counter() - t0) * 1000)


def _display(node, series, sub=None):
    parts = ["\\" + node.split(":", 1)[1], series.split(":", 1)[1] + "-series"]
    return " · ".join(parts + ([SHORT.get(sub, sub)] if sub else []))


def _quality(stages, t_start, gate_info, ctx_conf=0.0, ctx_source="session+graph", kept=(), total=0, lanes=None):
    scores = [c["score"] for c in kept]
    return {"claims_total": total, "claims_verified": len(kept), "dropped": total - len(kept),
            "support_avg": round(sum(scores) / len(scores), 3) if scores else 0,
            "support_min": round(min(scores), 3) if scores else 0,
            "gate": gate_info, "context_confidence": ctx_conf, "context_source": ctx_source,
            "sources_by_lane": lanes or {"doc": 0, "veteran": 0},
            "latency_ms": round((time.perf_counter() - t_start) * 1000), "stages_ms": dict(stages)}


def _all_experts(conn):
    """Fallback referral list when nothing in the graph matched: everyone, active first."""
    rows = _rows(conn, "SELECT * FROM person ORDER BY active DESC, name")
    return [{"id": r["id"], "name": r["name"], "role": r["role"], "team": r["team"], "years": r["years"],
             "expertise": r["expertise"] if isinstance(r["expertise"], list) else json.loads(r["expertise"] or "[]"),
             "availability": r["availability"], "contact": r["contact"],
             "reason": "Nothing in the knowledge base matches this question; ask the team.", "active": bool(r["active"])}
            for r in rows]


def _clarify(conn, question, kind, current=None):
    if kind == "node":
        rows = _rows(conn, "SELECT id, name FROM entity WHERE id LIKE 'node:%' ORDER BY id")
        return {"type": "clarify", "question": f"You are connected to {current} but mention another node. "
                                               "Which node do you mean?",
                "options": [{"label": "\\" + r["name"], "value": {"site": r["id"]}} for r in rows]}
    if kind == "vague":
        # only a whole subsystem matched ("the disk is acting up"): ask for the symptom, offer that area first
        ex = _rows(conn, "SELECT name FROM entity WHERE parent_id = %s AND kind IN ('event', 'object') "
                         "ORDER BY kind, id LIMIT 3", (current,))
        examples = "; ".join(r["name"] for r in ex)
        rows = _rows(conn, "SELECT id, name FROM entity WHERE id = %s", (current,))
        q = "Can you be more specific? What exactly are you seeing" + (f" (for example: {examples})" if examples else "")
        return {"type": "clarify", "question": q + "? Rephrase with the symptom, or continue with the general area:",
                "options": [{"label": r["name"], "value": {"system": r["id"]}} for r in rows]}
    rows = _rows(conn, "SELECT id, name FROM entity WHERE id LIKE 'sub:%' ORDER BY id")
    return {"type": "clarify", "question": "Which subsystem is this about?",
            "options": [{"label": r["name"], "value": {"system": r["id"]}} for r in rows]}


# ---------------------------------------------------------------- the pipeline
def answer(question, session, override=None):
    t_start, st = time.perf_counter(), {}
    override = {k: v for k, v in (override or {}).items() if v}
    node = override.get("site") or session["node"]
    series = override.get("version") or session["series"]
    with connect() as conn:
        t = time.perf_counter()
        r = resolve(conn, question, {"system": override.get("system"), "version": series, "site": node})
        _ms(st, "resolve", t)
        if not override.get("site") and any(n != session["node"] for n in r["nodes_mentioned"]):
            return _clarify(conn, question, "node", current="\\" + session["node"].split(":", 1)[1])
        sub = override.get("system") or r["subsystem"]
        if not sub:
            if r["entities"]:
                return _clarify(conn, question, "subsystem")
            # nothing in the graph matches at all: out of scope -> refer, with a context that carries no subsystem
            gate_info = {"sufficient": False, "reason": "no entity in the knowledge graph matches the question"}
            return {"type": "refer", "reason": "Nothing in the knowledge base matches this question.",
                    "context": {"system": "", "version": series, "site": node, "display": _display(node, series),
                                "confidence": 0.0},
                    "experts": _all_experts(conn),
                    "quality": _quality(st, t_start, gate_info, 0.0, "session+graph"),
                    "debug": {"stages_ms": st, "entities": []}}
        specific = any(e["kind"] in SPECIFIC for e in r["entities"])
        if not specific and not override.get("system"):
            return _clarify(conn, question, "vague", current=sub)
        ctx = {"system": sub, "version": series, "site": node}
        context = {**ctx, "display": _display(node, series, sub),
                   "confidence": 1.0 if override.get("system") else 0.9}
        ctx_source = "override" if override else "session+graph"

        t = time.perf_counter()
        lk = lookup(conn, [e["id"] for e in r["entities"]], ctx)
        _ms(st, "lookup", t)

        t = time.perf_counter()
        qvec = embed_query(question)
        hits = hybrid_search(conn, question, qvec, {"system": sub, "version": None, "site": None}, k=5)
        _ms(st, "search", t)

        # merge manual sections (graph-linked, then search hits; deduped, capped) and up to MAX_NOTES veteran notes,
        # interleaved doc/veteran. Notes-first made Qwen cite only veterans; docs-first made it cite only the manual.
        docs = {}
        for d in [*lk["doc_chunks"][:3], *hits]:
            docs.setdefault(d["id"], d["text"])
        doc_chunks = [{"id": i, "text": x, "lane": "doc"} for i, x in list(docs.items())[:MAX_DOCS]]
        notes = [{"id": h["id"], "text": h["text"], "lane": "veteran"} for h in lk["heuristics"][:MAX_NOTES]]
        chunks = [c for pair in zip_longest(doc_chunks, notes) for c in pair if c]
        lane_of = {c["id"]: c["lane"] for c in chunks}
        full = {c["id"]: c["text"] for c in chunks}
        lanes = {"doc": sum(c["lane"] == "doc" for c in chunks), "veteran": sum(c["lane"] == "veteran" for c in chunks)}
        gen_chunks = [{"id": c["id"], "text": c["text"][:GEN_CHARS], "lane": c["lane"]} for c in chunks]
        debug = {"entities": r["entities"], "path": lk["path"], "retrieved": [
            {"id": c["id"], "lane": c["lane"]} for c in chunks]}
        editions = dict(conn.execute("SELECT id, edition FROM doc_chunk WHERE id = ANY(%s)", (list(docs),)).fetchall())
        owners = {h["id"]: h["owner_name"] for h in lk["heuristics"]}
        for c in debug["retrieved"]:
            c["edition"], c["owner"] = editions.get(c["id"]), owners.get(c["id"])

        t = time.perf_counter()
        if specific and (lk["heuristics"] or lk["doc_chunks"]):
            # the graph pinned the question to a specific event/object with linked knowledge: skip the LLM gate
            # (saves ~2.7 s); generation can still return [] and MiniCheck still drops unsupported claims
            ok, reason = True, "graph match: " + ", ".join(e["name"] for e in r["entities"] if e["kind"] in SPECIFIC)
            st["gate"] = 0
        else:
            ok, g = gate.sufficient(question, gen_chunks)
            _ms(st, "gate", t)
            try:
                reason = json.loads(g["content"]).get("reason", "")
            except ValueError:
                reason = ""
        gate_info = {"sufficient": bool(ok), "reason": reason}
        debug["gate"] = gate_info

        def refer(why, kept=(), total=0):
            debug["stages_ms"] = st
            return {"type": "refer", "reason": why, "context": context, "experts": lk["experts"],
                    "quality": _quality(st, t_start, gate_info, context["confidence"], ctx_source, kept, total, lanes),
                    "debug": debug}

        if not ok:
            return refer(f"No verified answer for {context['display']}. {reason}".strip())

        t = time.perf_counter()
        claims, _ = generate.generate(question, gen_chunks, max_claims=MAX_CLAIMS)
        _ms(st, "generate", t)
        if claims is None:
            return refer(f"No verified answer for {context['display']}.")
        claims = [{**c, "claim": _clean(c["claim"])} for c in claims]
        cited, uncited = generate.keep_cited(claims, full)
        debug["dropped"] = [{"text": c["claim"], "source_id": c["source_id"], "score": None, "why": "uncited"}
                            for c in uncited]

        t = time.perf_counter()
        kept = []
        names = list(owners.values())
        wrong = [c for c in cited if misattributed(c["claim"], lane_of[c["source_id"]], names)]
        debug["dropped"] += [{"text": c["claim"], "source_id": c["source_id"], "score": None, "why": "misattributed"}
                             for c in wrong]
        cited = [c for c in cited if c not in wrong]
        # verify against the same text Qwen saw (GEN_CHARS), not the whole section: consistent and ~1 window per claim
        seen = {c["id"]: c["text"] for c in gen_chunks}
        scores = verify.support_probs([(seen[c["source_id"]], c["claim"]) for c in cited])
        for c, score in zip(cited, scores):
            if score >= VERIFY_THRESHOLD:
                kept.append({"text": c["claim"], "lane": lane_of[c["source_id"]], "source_id": c["source_id"],
                             "verified": True, "score": round(score, 3)})
            else:
                debug["dropped"].append({"text": c["claim"], "source_id": c["source_id"], "score": round(score, 3),
                                         "why": "unsupported"})
        _ms(st, "verify", t)
        total = len(claims)
        if not kept:
            return refer(f"No verified answer for {context['display']}.", total=total)

        used = list(dict.fromkeys(c["source_id"] for c in kept))
        sources = [source_card(conn, i) for i in used]
        lanes = {"doc": sum(lane_of[i] == "doc" for i in used), "veteran": sum(lane_of[i] == "veteran" for i in used)}
        log = conn.execute(
            "INSERT INTO answer_log (user_id, question, context, outcome, citations, dropped_claims) "
            "VALUES (%s, %s, %s::jsonb, 'answer', %s, %s) RETURNING id",
            (session.get("user", "newhire1"), question, json.dumps(context), used, total - len(kept))).fetchone()[0]
        conn.commit()
        debug["stages_ms"] = st
        return {"type": "answer", "answer_log_id": log, "context": context, "claims": kept, "sources": sources,
                "dropped_claims": total - len(kept), "experts": lk["experts"][:3],
                "quality": _quality(st, t_start, gate_info, context["confidence"], ctx_source, kept, total, lanes),
                "debug": debug}
