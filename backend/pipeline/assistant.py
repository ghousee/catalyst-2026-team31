"""Assistant-style answers (ANSWER_MODE=assistant): the standard RAG pattern, nothing clever.

  question (+ last turns) -> hybrid search over manual sections + vector search over veteran notes
  (notes HARD-filtered to the session node) -> cross-encoder rerank -> ONE LLM call that answers naturally
  and cites [n] after each sentence -> answer card with the cited sources and who to ask.

Safety that stays in code: notes outside the session node are never retrieved, so they can never be cited;
citations are mapped back to real source ids (unknown [n] are dropped); commands still come from the catalog
(separate /commands endpoint). See docs/ARCHITECTURE_V2.md.
"""
import json
import os
import re
import time

from backend.ingest.embedder import embed_query
from backend.pipeline import llm
from backend.pipeline.answer import _clean, _display, connect, source_card
from backend.pipeline.retrieve import hybrid_search

DOC_POOL = 20         # manual sections fetched by hybrid search before reranking
NOTE_POOL = 6         # veteran notes fetched by vector search before reranking
TOP_K = 5             # sources handed to the LLM after reranking
# small CPU cross-encoder (~0.7 s per question); bge-reranker-v2-m3 took 11-20 s on CPU, too slow here
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
HISTORY_TURNS = 3
SOURCE_CHARS = 1000   # per source sent to the LLM (shorter prompt = faster start)
MAX_ANSWER_TOKENS = 260  # ~120-180 words; long answers were most of the latency

_rr = None


def _reranker():
    global _rr
    if _rr is None:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        tok = AutoTokenizer.from_pretrained(RERANK_MODEL)
        mdl = AutoModelForSequenceClassification.from_pretrained(RERANK_MODEL).eval()
        _rr = (torch, tok, mdl)
    return _rr


def rerank(query, texts, max_len=384):
    """Relevance in 0..1 for each text (cross-encoder, sigmoid of the logit)."""
    if not texts:
        return []
    torch, tok, mdl = _reranker()
    with torch.no_grad():
        enc = tok([query] * len(texts), texts, padding=True, truncation=True, max_length=max_len, return_tensors="pt")
        return torch.sigmoid(mdl(**enc).logits.view(-1)).tolist()


def warm():
    _reranker()


# ---------------------------------------------------------------- retrieval
def note_text(n):
    scope = "\\" + n["site_id"].split(":", 1)[1] if n.get("site_id") else "all nodes"
    parts = [f"When: {n['trigger_text']}", f"Do: {n['call_text']}"]
    if n.get("why_text"):
        parts.append(f"Why: {n['why_text']}")
    if n.get("not_when_text"):
        parts.append(f"Does not apply when: {n['not_when_text']}")
    return f"{n['owner_name']} ({n['owner_role']}, {n['years']} yrs), applies to {scope}. " + " ".join(parts)


def search_notes(conn, qvec, node, k=NOTE_POOL):
    """Approved veteran notes for this node (or all nodes), nearest first. Notes for other nodes are never returned."""
    cur = conn.execute(
        """SELECT h.id, h.owner_id, h.system_id, h.site_id, h.trigger_text, h.call_text, h.why_text, h.not_when_text,
                  p.name AS owner_name, p.role AS owner_role, p.years
           FROM heuristic h JOIN person p ON p.id = h.owner_id
           WHERE h.status = 'approved' AND (h.site_id = %(node)s OR h.site_id IS NULL)
           ORDER BY h.embedding <=> %(q)s::vector LIMIT %(k)s""", {"node": node, "q": qvec, "k": k})
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def retrieve(conn, query, node):
    """Top TOP_K sources by reciprocal-rank fusion of the search order and the reranker order. The reranker's raw
    score is never used to discard sources (the small cross-encoder scores typo'd or vague questions near 0 even
    when search found the right sections); the LLM decides whether the sources answer the question."""
    qvec = embed_query(query)
    docs = [{"id": d["id"], "kind": "doc", "system_id": d["system_id"], "text": f"{d['section']}\n{d['text']}"}
            for d in hybrid_search(conn, query, qvec, None, k=DOC_POOL)]
    notes = [{"id": n["id"], "kind": "note", "system_id": n["system_id"], "text": note_text(n), "owner": n["owner_name"]}
             for n in search_notes(conn, qvec, node)]
    for lst in (docs, notes):
        for i, c in enumerate(lst):
            c["search_rank"] = i
    cands = docs + notes
    for c, s in zip(cands, rerank(query, [c["text"] for c in cands])):
        c["score"] = s
    for i, c in enumerate(sorted(cands, key=lambda c: -c["score"])):
        c["fused"] = 1 / (60 + c["search_rank"]) + 1 / (60 + i)
    ranked = sorted(cands, key=lambda c: -c["fused"])
    return ranked[:TOP_K], ranked[:TOP_K]


# ---------------------------------------------------------------- answer
SYSTEM = """You are CAIL's assistant for HPE NonStop operators. The operator is working on node {node} ({series}).
The numbered sources are the retrieved HPE manual sections and senior operators' notes (the operator did not write
them). Answer using ONLY those sources. Write like an experienced colleague: start with the direct answer, then the
steps, in plain short sentences. Be concise: about 120 words unless the operator asks for more detail. Put the source number in brackets after every sentence that uses a source, e.g. [2].
VETERAN sources are field experience from named senior operators: when you use one, say whose advice it is
(e.g. "Maria Rossi's advice:") and keep its meaning exactly, including every "do not". MANUAL sources are HPE manual
sections; manual editions may be older than the operator's system.
Use a source only if it directly answers the question; ignore sources that are merely related. Using no source
at all is fine. If the question is vague (no system, symptom or error named), do not list general advice: ask one
short question about what they are seeing.
If the sources do not answer the question, say plainly that the manuals and captured knowledge don't cover it,
do not guess, and suggest who to ask: {experts}.
If the question is too vague to answer, ask one short clarifying question.
If the message is only a greeting or thanks, reply in one or two sentences and say what you can help with.
Never invent commands, numbers, node names or facts that are not in the sources."""


def build_messages(question, sources, node, series, experts, history=()):
    src = "\n\n".join(f"[{i + 1}] {'VETERAN' if s['kind'] == 'note' else 'MANUAL'}: {s['text'][:SOURCE_CHARS]}"
                      for i, s in enumerate(sources)) or "(no sources matched)"
    msgs = [{"role": "system", "content": SYSTEM.format(node=node, series=series, experts=experts or "the on-call team")}]
    for h in list(history)[-HISTORY_TURNS:]:
        if h.get("question"):
            msgs.append({"role": "user", "content": h["question"]})
        if h.get("reply"):
            msgs.append({"role": "assistant", "content": h["reply"]})
    msgs.append({"role": "user", "content": f"Sources:\n\n{src}\n\nQuestion: {question}"})
    return msgs


_CITE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def map_citations(text, sources):
    """Keep only [n] that point to a real source; returns (text, {n: source_id}, cited ids in order)."""
    ok, order = {}, []

    def sub(m):
        nums = [int(x) for x in re.findall(r"\d+", m.group(1)) if 1 <= int(x) <= len(sources)]
        for n in nums:
            ok[str(n)] = sources[n - 1]["id"]
            if sources[n - 1]["id"] not in order:
                order.append(sources[n - 1]["id"])
        return "[" + ", ".join(map(str, nums)) + "]" if nums else ""
    return _CITE.sub(sub, text).strip(), ok, order


def experts_for(conn, subsystems, note_owner_names):
    """People to ask: owners of the notes used first, then the strongest expert_in links for these subsystems."""
    if not subsystems:
        rows = conn.execute("SELECT id, name, role, team, years, expertise, availability, contact, active FROM person "
                            "ORDER BY active DESC, name").fetchall()
        weights = {}
    else:
        rows = conn.execute(
            """SELECT p.id, p.name, p.role, p.team, p.years, p.expertise, p.availability, p.contact, p.active,
                      max(e.weight) AS w
               FROM person p JOIN edge e ON e.src = p.id AND e.rel = 'expert_in'
               WHERE e.dst = ANY(%s) GROUP BY p.id ORDER BY max(e.weight) DESC""", (list(subsystems),)).fetchall()
        weights = {r[0]: r[9] for r in rows}
    out = []
    for r in rows:
        used = r[1] in note_owner_names
        reason = ("their captured knowledge is cited above" if used else
                  f"expert in this area (up to {int(weights[r[0]])} resolved cases)" if r[0] in weights else "on the team")
        out.append({"id": r[0], "name": r[1], "role": r[2], "team": r[3], "years": r[4],
                    "expertise": r[5] if isinstance(r[5], list) else json.loads(r[5] or "[]"),
                    "availability": r[6], "contact": r[7], "reason": reason, "active": bool(r[8])})
    order = {"on_shift": 0, "on_call": 1, "off_shift": 2, "retired": 3}
    return sorted(out, key=lambda e: (not (e["name"] in note_owner_names), order.get(e["availability"], 4)))[:3]


_OTHER_NODE = re.compile(r"(?<![a-z0-9])\\?(prod|dr)(?![a-z0-9])", re.I)


def answer(question, session, override=None, history=()):
    t0, st = time.perf_counter(), {}
    override = {k: v for k, v in (override or {}).items() if v}
    node = override.get("site") or session["node"]
    series = override.get("version") or session["series"]
    mentioned = {"node:" + m.upper() for m in _OTHER_NODE.findall(question)}
    if not override.get("site") and mentioned and node not in mentioned:
        return {"type": "clarify", "question": f"You are connected to \\{node.split(':', 1)[1]} but mention another node. "
                                               "Which node do you mean?",
                "options": [{"label": "\\PROD", "value": {"site": "node:PROD"}}, {"label": "\\DR", "value": {"site": "node:DR"}}]}
    # short follow-ups ("why?", "what about the commands?") are searched together with the previous question
    last = next((h["question"] for h in reversed(list(history)) if h.get("question")), "")
    query = f"{last} {question}" if last and len(question.split()) <= 6 else question

    with connect() as conn:
        t = time.perf_counter()
        sources, top_raw = retrieve(conn, query, node)
        st["retrieve_rerank"] = round((time.perf_counter() - t) * 1000)
        subs = list(dict.fromkeys(s["system_id"] for s in sources)) or list(dict.fromkeys(s["system_id"] for s in top_raw[:2]))
        experts = experts_for(conn, subs, {s["owner"] for s in sources if s["kind"] == "note"})
        names = ", ".join(f"{e['name']} ({e['availability'] or 'available'})" for e in experts if e["availability"] != "retired")

        t = time.perf_counter()
        r = llm.chat(build_messages(question, sources, "\\" + node.split(":", 1)[1], series.split(":", 1)[1] + "-series",
                                    names, history), temperature=0.2, max_tokens=MAX_ANSWER_TOKENS)
        st["generate"] = round((time.perf_counter() - t) * 1000)
        reply, cites, used = map_citations(_clean(r["content"]), sources)

        sub = subs[0] if subs else ""
        context = {"system": sub, "version": series, "site": node, "display": _display(node, series, sub or None),
                   "confidence": round(max((s["score"] for s in sources), default=0.0), 2)}  # top reranker relevance
        cards = [c for c in (source_card(conn, i) for i in used) if c]
        lanes = {"doc": sum(1 for i in used if i.startswith("doc:")), "veteran": sum(1 for i in used if not i.startswith("doc:"))}
        log = conn.execute(
            "INSERT INTO answer_log (user_id, question, context, outcome, citations, dropped_claims) "
            "VALUES (%s, %s, %s::jsonb, 'answer', %s, 0) RETURNING id",
            (session.get("user", "newhire1"), question, json.dumps(context), used)).fetchone()[0]
        conn.commit()
    st["total"] = round((time.perf_counter() - t0) * 1000)
    return {"type": "answer", "answer_log_id": log, "context": context, "reply": reply, "reply_citations": cites,
            "claims": [], "sources": cards, "dropped_claims": 0, "experts": experts,
            "quality": {"mode": "assistant", "sources_by_lane": lanes, "sources_considered": len(sources),
                        "top_relevance": context["confidence"], "latency_ms": st["total"], "stages_ms": st},
            "debug": {"retrieved": [{"id": s["id"], "kind": s["kind"], "rerank": round(s["score"], 3),
                               "search_rank": s["search_rank"]} for s in top_raw],
                      "query": query}}
