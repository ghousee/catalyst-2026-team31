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
from backend.graph.query import _captured, fetch_notes, lookup, note_search, resolve, scope_text, short
from backend.ingest.embedder import embed_query
from backend.pipeline import gate, generate, verify
from backend.pipeline.retrieve import hybrid_search, query_terms

VERIFY_THRESHOLD = float(os.getenv("VERIFY_THRESHOLD", "0.5"))
GEN_CHARS = 1800   # per-source text handed to Qwen (MiniCheck sees the full text)
MAX_DOCS = 6
MAX_CLAIMS = 4     # fewer claims = faster generation + verification
MAX_NOTES = 3      # veteran notes per answer (lookup returns them most-relevant first)
# a veteran note is a candidate only if its embedding is this close (cosine) to the question. Calibrated on the real
# questions: off-topic notes scored 0.31-0.49, on-topic ones 0.55-0.79 (vault/code/api.md)
NOTE_MIN_SIM = float(os.getenv("NOTE_MIN_SIM", "0.5"))
# at or above this cosine the note is clearly about the question: MiniCheck is not asked (it scores a faithful
# negation paraphrase like "do not start with X" at 0.02, so it is only a tie-breaker in the 0.5-0.7 band)
NOTE_STRONG_SIM = float(os.getenv("NOTE_STRONG_SIM", "0.7"))
SPECIFIC = {"event", "object", "command", "metric"}  # entity kinds that pin a question down
VAGUE_TERMS = 5    # unmatched questions with this few content words get a clarifying question

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


def relevant_notes(ids, sims, min_sim=NOTE_MIN_SIM):
    """Candidate note ids whose cosine similarity to the question reaches min_sim (unknown similarity = not relevant)."""
    return [i for i in ids if sims.get(i, 0.0) >= min_sim]


def note_ok(score, sim, verify_threshold=VERIFY_THRESHOLD):
    """Keep a note Qwen cited: Qwen's claim about it is supported by the note text, or the note is a very close match."""
    return score >= verify_threshold or (sim or 0.0) >= NOTE_STRONG_SIM


def note_plain(n):
    """The veteran's own words without the card header (owner, scope, ...): what a claim about the note is checked against."""
    return " ".join(x for x in (n.get("trigger"), n.get("call"), n.get("why"), n.get("not_when")) if x) or n["text"]


def clean_title(s):
    """Display-clean the kerning glitch of the TACL text extraction: 'Com m and(s)' -> 'Command(s)', 'Com ments' -> 'Comments'."""
    return re.sub(r"\bCom\s?m\s?(and|ent)", r"Comm\1", s or "")


def verbatim(note, max_chars=300):
    """The veteran's own call text; very long ones are cut to the first 2 sentences. Never a paraphrase."""
    t = (note["call"] or "").strip()
    return t if len(t) <= max_chars else " ".join(re.split(r"(?<=[.!?])\s+", t)[:2])


def veteran_claims(cited_ids, notes, pool, doc_cited=None):
    """One verbatim claim per cited note, plus the verbatim claim of any in-context note it disagrees with
    (both marked conflict_with); a note that contradicts a manual section also carries contradicts=<doc id>.
    cited_ids: note ids Qwen cited (in order); notes: {id: note} usable now; pool: {id: note} incl. partners.
    `contradicts` is set only when that manual section is among the answer's cited docs (doc_cited; None = no check).
    A note flagged needs_review (its manual section changed since signing) carries needs_review=True."""
    ids = [i for i in cited_ids if i in notes]
    for i in list(ids):
        ids += [o for o in notes[i]["disagrees_with"] if o in pool and o not in ids]
    out = []
    for i in ids:
        n = pool[i]
        c = {"text": verbatim(n), "lane": "veteran", "source_id": i, "verified": True, "score": 1.0, "verbatim": True}
        other = next((o for o in n["disagrees_with"] if o in ids), None)
        if other:
            c["conflict_with"] = other
        if n["relation"].startswith("contradicts:") and (
                doc_cited is None or n["relation"].split(":", 1)[1] in doc_cited):
            c["contradicts"] = n["relation"].split(":", 1)[1]
        if n.get("needs_review"):
            c["needs_review"] = True
        out.append(c)
    return out


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
    # no params -> pass None, else psycopg reads a literal '%' (LIKE 'sub:%') as a placeholder and raises
    cur = conn.execute(sql, params or None)
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
        return {"id": d["id"], "kind": "doc", "title": edition.split(",")[0] or clean_title(d["section"]) or d["id"],
                "part_number": d["doc_version"], "section": clean_title(d["section"]), "applies_to": edition,
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
            "last_validated": str(h["last_validated"] or ""), "scope": scope_text(h), "why": h["why_text"] or "",
            "not_when": h["not_when_text"] or "", "needs_review": bool(h["needs_review"])}
    if rel:
        card["relation"] = f"{rel[0]['rel']}:{rel[0]['dst']}"
    return card


# ---------------------------------------------------------------- small helpers
def _ms(stages, name, t0):
    stages[name] = round((time.perf_counter() - t0) * 1000)


def _display(node, series, sub=None):
    parts = ["\\" + node.split(":", 1)[1], series.split(":", 1)[1] + "-series"]
    return " · ".join(parts + ([short(sub)] if sub else []))


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
    rows = _rows(conn, "SELECT id, name FROM entity WHERE id LIKE 'sub:%' ORDER BY id")
    q = ("Can you be more specific? Which system is this about, and what exactly are you seeing "
         "(an EMS event number, an error text, a command output)?" if kind == "vague"
         else "Which subsystem is this about?")
    return {"type": "clarify", "question": q,
            "options": [{"label": r["name"], "value": {"system": r["id"]}} for r in rows]}


def is_vague(question):
    """Too little to go on ("its slow", "how do i fix it"): at most VAGUE_TERMS content words."""
    return len(query_terms(question)) <= VAGUE_TERMS


def subsystem_from_hits(hits, min_share=3):
    """Subsystem most of the top manual hits agree on (>= min_share of them), else None."""
    counts = {}
    for h in hits:
        counts[h["system_id"]] = counts.get(h["system_id"], 0) + 1
    best = max(counts.items(), key=lambda kv: kv[1], default=(None, 0))
    return best[0] if best[1] >= min_share else None


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
        qvec = None
        if not sub and not r["entities"]:
            # nothing in the graph matched: too vague -> ask; otherwise let the manuals say which subsystem it is
            if is_vague(question):
                return _clarify(conn, question, "vague")
            t = time.perf_counter()
            qvec = embed_query(question)
            sub = subsystem_from_hits(hybrid_search(conn, question, qvec, None, k=5))
            _ms(st, "infer_subsystem", t)
            if not sub:
                gate_info = {"sufficient": False, "reason": "no entity in the knowledge graph matches the question"}
                return {"type": "refer", "reason": "Nothing in the knowledge base matches this question.",
                        "context": {"system": "", "version": series, "site": node, "display": _display(node, series),
                                    "confidence": 0.0},
                        "experts": _all_experts(conn),
                        "quality": _quality(st, t_start, gate_info, 0.0, "session+graph"),
                        "debug": {"stages_ms": st, "entities": []}}
        if not sub:
            return _clarify(conn, question, "subsystem")
        # specific = the graph pinned an event/object/command/metric; subsystem-only matches go through the LLM gate
        specific = any(e["kind"] in SPECIFIC for e in r["entities"])
        ctx = {"system": sub, "version": series, "site": node}
        context = {**ctx, "display": _display(node, series, sub),
                   "confidence": 1.0 if override.get("system") else 0.9}
        ctx_source = "override" if override else "session+graph"

        t = time.perf_counter()
        lk = lookup(conn, [e["id"] for e in r["entities"]], ctx)
        _ms(st, "lookup", t)

        t = time.perf_counter()
        qvec = qvec or embed_query(question)
        hits = hybrid_search(conn, question, qvec, {"system": sub, "version": None, "site": None}, k=5)
        _ms(st, "search", t)

        # merge manual sections (graph-linked, then search hits; deduped, capped) and up to MAX_NOTES veteran notes,
        # interleaved doc/veteran. Notes-first made Qwen cite only veterans; docs-first made it cite only the manual.
        docs = {}
        for d in [*lk["doc_chunks"][:3], *hits]:
            docs.setdefault(d["id"], d["text"])
        editions = dict(conn.execute("SELECT id, edition FROM doc_chunk WHERE id = ANY(%s)", (list(docs),)).fetchall())
        doc_chunks = [{"id": i, "text": x, "lane": "doc", "edition": editions.get(i)} for i, x in list(docs.items())[:MAX_DOCS]]
        # veteran notes: graph-linked (lookup) plus the nearest by vector; the search's best hit goes in even when
        # the graph already linked enough notes
        found = note_search(conn, qvec, ctx, k=20)  # every in-context note with its cosine score
        sims = {h["id"]: h["score"] for h in found}
        pool = {h["id"]: h for h in [*lk["heuristics"], *found]}
        order = list(dict.fromkeys([h["id"] for h in [*lk["heuristics"][:2], *found, *lk["heuristics"][2:]]]))
        dropped_notes = [i for i in order if i not in relevant_notes(order, sims)]
        order = relevant_notes(order, sims)[:MAX_NOTES]
        notes = [{"id": i, "text": pool[i]["text"], "lane": "veteran"} for i in order]
        chunks = [c for pair in zip_longest(doc_chunks, notes) for c in pair if c]
        lane_of = {c["id"]: c["lane"] for c in chunks}
        full = {c["id"]: c["text"] for c in chunks}
        lanes = {"doc": sum(c["lane"] == "doc" for c in chunks), "veteran": sum(c["lane"] == "veteran" for c in chunks)}
        gen_chunks = [{**c, "text": c["text"][:GEN_CHARS]} for c in chunks]
        debug = {"entities": r["entities"], "path": lk["path"], "retrieved": [
            {"id": c["id"], "lane": c["lane"]} for c in chunks],
            "note_sims": {i: sims.get(i) for i in order}, "notes_below_cutoff": {i: sims.get(i) for i in dropped_notes}}
        owners = {h["id"]: h["owner_name"] for h in pool.values()}
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
        names = list(owners.values())
        seen = {c["id"]: c["text"] for c in gen_chunks}
        # veteran claims are never Qwen's wording: a note Qwen cited becomes one verbatim claim, but only if Qwen's own
        # claim about it is supported by the note text (an off-topic note Qwen cited out of habit fails here); the
        # wording is then replaced by the note's call_text (MiniCheck scored an inverting paraphrase at 0.97).
        vet_claims = [c for c in cited if lane_of[c["source_id"]] == "veteran"]
        doc_claims = [c for c in cited if lane_of[c["source_id"]] == "doc"]
        wrong = [c for c in doc_claims if misattributed(c["claim"], "doc", names)]
        neg = [c for c in doc_claims if c not in wrong and verify.negation_mismatch(c["claim"], seen[c["source_id"]])]
        debug["dropped"] += [{"text": c["claim"], "source_id": c["source_id"], "score": None, "why": "misattributed"}
                             for c in wrong]
        debug["dropped"] += [{"text": c["claim"], "source_id": c["source_id"], "score": None, "why": "negation"}
                             for c in neg]
        doc_claims = [c for c in doc_claims if c not in wrong and c not in neg]
        kept = []
        # verify against the same text Qwen saw (GEN_CHARS), not the whole section: consistent and ~1 window per claim
        scores = verify.support_probs([(note_plain(pool[c["source_id"]]), c["claim"]) for c in vet_claims] +
                                      [(seen[c["source_id"]], c["claim"]) for c in doc_claims])
        vet_scores, scores = scores[:len(vet_claims)], scores[len(vet_claims):]
        cited_notes = []
        for c, score in zip(vet_claims, vet_scores):
            if note_ok(score, sims.get(c["source_id"])):
                if c["source_id"] not in cited_notes:
                    cited_notes.append(c["source_id"])
            else:
                debug["dropped"].append({"text": c["claim"], "source_id": c["source_id"], "score": round(score, 3),
                                         "why": "note_unsupported"})
        for c, score in zip(doc_claims, scores):
            if score >= VERIFY_THRESHOLD:
                kept.append({"text": c["claim"], "lane": "doc", "source_id": c["source_id"],
                             "verified": True, "score": round(score, 3)})
            else:
                debug["dropped"].append({"text": c["claim"], "source_id": c["source_id"], "score": round(score, 3),
                                         "why": "unsupported"})
        # disagreement partners must be in the context too (note_search/lookup may not have returned them)
        partners = [o for i in cited_notes for o in pool[i]["disagrees_with"] if o not in pool]
        pool.update(fetch_notes(conn, partners, ctx))
        for i in pool:
            lane_of.setdefault(i, "veteran")
        vets = veteran_claims(cited_notes, {i: pool[i] for i in cited_notes}, pool,
                              doc_cited={c["source_id"] for c in kept})
        kept = vets + kept  # the operator-specific advice first, then the manual's facts
        _ms(st, "verify", t)
        total = len(kept) + len(debug["dropped"])
        if not kept:
            return refer(f"No verified answer for {context['display']}.", total=total)

        used = list(dict.fromkeys(c["source_id"] for c in kept))
        sources = [source_card(conn, i) for i in used]
        lanes = {"doc": sum(lane_of[i] == "doc" for i in used), "veteran": sum(lane_of[i] == "veteran" for i in used)}
        log = conn.execute(
            "INSERT INTO answer_log (user_id, question, context, outcome, citations, dropped_claims) "
            "VALUES (%s, %s, %s::jsonb, 'answer', %s, %s) RETURNING id",
            (session.get("user", "newhire1"), question, json.dumps(context), used, len(debug["dropped"]))).fetchone()[0]
        conn.commit()
        debug["stages_ms"] = st
        return {"type": "answer", "answer_log_id": log, "context": context, "claims": kept, "sources": sources,
                "dropped_claims": len(debug["dropped"]), "experts": lk["experts"][:3],
                "quality": _quality(st, t_start, gate_info, context["confidence"], ctx_source, kept, total, lanes),
                "debug": debug}
