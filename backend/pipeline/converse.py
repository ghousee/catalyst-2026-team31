"""Conversational layer around the verified answer: reply text, follow-up memory, status questions, refer next steps.

Nothing here adds facts. The reply is written from the already-verified claims and rejected by simple checks if it
introduces anything they do not contain; follow-up memory only chooses what to retrieve for (node scoping is untouched).
"""
import re

from backend.pipeline import llm
from backend.pipeline.retrieve import query_terms

REPLY_TOKENS = 120
SHORT_TERMS = 2      # a follow-up with this few content words ("why?", "what about on DR?") needs the previous question
MAX_HISTORY = 3

REPLY_SYSTEM = (
    "You are a NonStop operations assistant talking to an operator. Write a short reply of 2 to 5 sentences in plain "
    "English, addressed to 'you', starting with the direct answer to the question. Use ONLY the numbered facts. "
    "Put the fact number in square brackets, like [1], before the full stop of every sentence that uses a fact. "
    "Do not add any number, command name, node name or advice that is not in the facts. Keep every 'do not' and "
    "condition exactly. If facts conflict, say the experts disagree. No lists, no headings.")


# ---------------------------------------------------------------- reply
def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text.strip()) if s.strip()]


_UPPER = re.compile(r"\$?[A-Za-z0-9]*[A-Z][A-Z0-9_$]{2,}\b|\\[A-Za-z]+")  # TMFCOM, FILESPERVOLUME, $AUDIT, \PROD
_NUM = re.compile(r"\d+(?:\.\d+)?")
_NEG = re.compile(r"\b(?:do not|don't|never|must not|should not|shouldn't|not)\b", re.I)


def reply_ok(reply, claims, extra=""):
    """True if the reply is safe to show. claims = kept claims in order; extra = context text the reply may also name
    (node, subsystem). Rules: every sentence carries a valid [n] marker; no number, command/node-like word that is not in
    the claims; a 'do not' in a claim must survive as a negation."""
    if not reply or not claims or reply.rstrip()[-1] not in ".!?":
        return False
    facts = " ".join(c["text"] for c in claims) + " " + extra
    for s in _sentences(reply):
        marks = [int(m) for m in re.findall(r"\[(\d+)\]", s)]
        if not marks or any(not 1 <= m <= len(claims) for m in marks):
            return False
    body = re.sub(r"\[\d+\]", "", reply)
    nums = set(_NUM.findall(facts))
    if any(n not in nums for n in _NUM.findall(body)):
        return False
    low = facts.lower()
    if any(w.lower().lstrip("\\$") not in low.replace("\\", "").replace("$", "") for w in _UPPER.findall(body)):
        return False
    if any(_NEG.search(c["text"]) for c in claims) and not _NEG.search(body):
        return False
    return True


def reply_citations(reply, claims):
    """{"1": source_id, ...} for the markers the reply uses (marker n = n-th kept claim)."""
    used = sorted({int(m) for m in re.findall(r"\[(\d+)\]", reply)})
    return {str(n): claims[n - 1]["source_id"] for n in used if 1 <= n <= len(claims)}


def write_reply(question, claims, extra="", history_q=None):
    """One short Qwen call. Returns (reply, citations) or (None, {}) when the call fails or the guard rejects it."""
    facts = "\n".join(f"[{i + 1}] {c['text']}" for i, c in enumerate(claims))
    ask = f"Earlier question: {history_q}\nFollow-up: {question}" if history_q else f"Question: {question}"
    try:
        r = llm.chat([{"role": "system", "content": REPLY_SYSTEM},
                      {"role": "user", "content": f"Facts:\n{facts}\n\n{ask}\nReply:"}],
                     num_ctx=4096, max_tokens=REPLY_TOKENS, think=False)
    except Exception:  # the reply is a nicety: never fail the answer because of it
        return None, {}
    text = r["content"].strip()
    return (text, reply_citations(text, claims)) if reply_ok(text, claims, extra) else (None, {})


# ---------------------------------------------------------------- follow-up memory
def is_short(question):
    return len(query_terms(question)) <= SHORT_TERMS


def previous_question(history):
    """The latest earlier question that stands on its own (not itself a 'why?')."""
    return next((t["question"] for t in reversed((history or [])[-MAX_HISTORY:])
                 if t.get("question") and not is_short(t["question"])), None)


def last_system(history):
    return next((t["context"]["system"] for t in reversed((history or [])[-MAX_HISTORY:])
                 if (t.get("context") or {}).get("system")), None)


def followup_text(question, history):
    """Question text to retrieve with: a short follow-up ("why?", "what about on DR?") gets the previous question
    prepended. None when this is not a short follow-up. Scoping (node, series) is applied later, as for any question."""
    prev = previous_question(history)
    return f"{prev} {question}" if prev and is_short(question) else None


# ---------------------------------------------------------------- status questions
_STATUS = re.compile(r"\b(?:is|are)\b.{0,40}\b(?:healthy|ok|okay|up|down|running|working|fine|alive)\b"
                     r"|\bstatus\s+of\b|\bhealth\s+of\b|\bhow\s+is\b.{0,30}\b(?:doing|running)\b", re.I)


def is_status_question(question):
    return bool(_STATUS.search(question or ""))


# metric ids the simulator serves, per subsystem (the simulator has no Pathway/Storage feed)
LIVE_METRICS = {"sub:TMF": ["audit-capacity-pct"], "sub:MEASURE": ["cpu-busy-time", "request-qtime"],
                "sub:PEEK": ["cpu-busy-time"]}


def live_metrics(system, metrics):
    """Latest simulated value of the metrics for this subsystem. metrics = simulator.metrics() output."""
    want = LIVE_METRICS.get(system, [])
    return [{"metric": s["metric"], "value": s["points"][-1][1], "ts": s["points"][-1][0]}
            for s in metrics["series"] if s["metric"] in want and s["points"]]


def status_reply(name, node, live, commands):
    """Deterministic status text: states only what the simulated feed shows, never a verdict."""
    cmds = ", ".join(commands)
    if live:
        vals = "; ".join(f"{m['metric']} {m['value']}" for m in live)
        text = f"Simulated live data for {node} · {name}: {vals}. This is a simulated feed, not a real system."
        return text + (f" To check the real state, run these read-only checks: {cmds}." if cmds else "")
    text = f"I can't see a live {name} feed for {node} yet, so I can't tell its current state."
    return text + (f" Run these read-only checks: {cmds}." if cmds else "")


# ---------------------------------------------------------------- helpful refer
AVAIL = {"on_shift": "on shift", "on_call": "on call", "off_shift": "off shift", "retired": "retired"}


def refer_next_steps(commands, limit=3):
    """commands = [(command_text, explanation)] read-only catalog entries -> short next-step strings."""
    return [f"Run {cmd} (read-only): {expl.split('; ')[0].rstrip('.')}." for cmd, expl in commands[:limit]]


def refer_reply(display, steps, experts, subsystem_known=True):
    head = (f"I don't have verified knowledge for this on {display}." if subsystem_known
            else "Nothing in the knowledge base matches this question.")
    text = head + (" Next: " + " ".join(steps) if steps else "")
    if experts:
        e = experts[0]
        avail = f" ({AVAIL[e['availability']]})" if e.get("availability") in AVAIL else ""
        text += f" {e['name']}{avail} knows this system." if subsystem_known else f" Ask {e['name']}{avail}."
    return text
