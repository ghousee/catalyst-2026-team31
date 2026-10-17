"""Step 3: sufficiency gate - is the retrieved context enough to answer? No -> refer to a person."""
import json

from backend.pipeline import llm

GATE_SCHEMA = {"type": "object",
               "properties": {"sufficient": {"type": "boolean"}, "reason": {"type": "string", "maxLength": 160}},
               "required": ["sufficient", "reason"]}

SYSTEM = ("You are a strict gatekeeper for a NonStop operations assistant. Decide whether the sources contain "
          "the specific information needed to answer the question. Answer sufficient=true only if a "
          "correct, specific answer can be written from the sources alone; related-but-different topics, "
          "or a different command/subsystem than the one asked about, are NOT sufficient. The reason is one short sentence (max 20 words).")


def build_messages(question, chunks, max_chars=3000):
    src = "\n\n".join(f"[source_id: {c['id']}]\n{c['text'][:max_chars]}" for c in chunks)
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Sources:\n\n{src}\n\nQuestion: {question}\n"
                                        "Are the sources sufficient to answer? JSON:"}]


def parse_gate(text):
    try:
        d = json.loads(text)
        return bool(d["sufficient"])
    except (ValueError, KeyError, TypeError):
        return None


def sufficient(question, chunks, num_ctx=8192, **kw):
    """Returns (bool_or_None, llm_stats)."""
    r = llm.chat(build_messages(question, chunks), schema=GATE_SCHEMA, num_ctx=num_ctx, max_tokens=200, **kw)
    return parse_gate(r["content"]), r
