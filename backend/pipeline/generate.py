"""Step 4: Qwen writes the answer as JSON [{claim, source_id}] from retrieved chunks only.

Claims whose source_id is not one of the retrieved ids are dropped by code (CLAUDE.md rule 1).
"""
import json

from backend.pipeline import llm

CLAIMS_SCHEMA = {
    "type": "array",
    "maxItems": 6,  # unbounded arrays let a 4B model loop until the token limit (seen in the spike)
    "items": {"type": "object",
              "properties": {"claim": {"type": "string"}, "source_id": {"type": "string"}},
              "required": ["claim", "source_id"]},
}

SYSTEM = ("You answer NonStop operator questions using ONLY the numbered sources. "
          "Return a JSON array of short factual claims; each claim must cite the id of the single source that "
          "supports it in source_id (copy the id exactly). Do not state anything the sources do not say. "
          "If the sources do not answer the question, return an empty array [].")
# Added when sources carry a lane (MANUAL / VETERAN): answers must cite both kinds, and never put a veteran's
# advice in the manual's mouth (seen in testing: "the manual recommends X" cited to a veteran note saying not-X).
LANE_RULES = (" Sources are marked MANUAL or VETERAN. If both kinds are given, return a balanced answer: about "
              "half the claims from MANUAL sources and half from VETERAN sources (for example 2 and 2), choosing "
              "the claims that best tell the operator what is happening and what to do. Phrase VETERAN claims as "
              "the veteran's advice (for example 'Experienced operators check ...'), never as what the manual "
              "says, and keep their meaning exactly, including any 'do not'.")


def label(i, alias):
    return f"S{i + 1}" if alias else None


def build_messages(question, chunks, max_chars=3500, alias=True):
    """chunks: [{id, text, lane?}]. Each source is truncated to max_chars to bound the prompt.

    alias=True labels sources S1..Sn instead of their long ids (the model copies short labels reliably;
    with raw ids it invented ids derived from message numbers inside merged chunks). Use unalias() after.
    Optional lane ("doc" / "veteran") is shown as MANUAL / VETERAN; a doc's optional edition follows MANUAL.
    """
    def head(i, c):
        lane = {"doc": " | MANUAL", "veteran": " | VETERAN"}.get(c.get("lane"), "")
        if c.get("lane") == "doc" and c.get("edition"):
            lane += f" | {c['edition']}"  # so Qwen does not overstate an older edition as current behaviour
        return f"[source_id: {label(i, alias) or c['id']}{lane}]"
    src = "\n\n".join(f"{head(i, c)}\n{c['text'][:max_chars]}" for i, c in enumerate(chunks))
    system = SYSTEM + (LANE_RULES if any(c.get("lane") for c in chunks) else "")
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"Sources:\n\n{src}\n\nQuestion: {question}\nJSON:"}]


def unalias(claims, chunks):
    """Map S1..Sn labels back to chunk ids; unknown labels are left as-is (and later dropped as invalid)."""
    m = {f"S{i + 1}": c["id"] for i, c in enumerate(chunks)}
    return [{"claim": c["claim"], "source_id": m.get(c["source_id"].strip("[] "), c["source_id"])} for c in claims]


def parse_claims(text):
    """Parsed [{claim, source_id}] or None if the text is not valid JSON of that shape."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, list):
        return None
    for d in data:
        if not (isinstance(d, dict) and isinstance(d.get("claim"), str) and isinstance(d.get("source_id"), str)):
            return None
    return data


def keep_cited(claims, valid_ids):
    """Split claims into (kept, dropped) by whether source_id is one of the retrieved ids."""
    valid = set(valid_ids)
    kept = [c for c in claims if c["source_id"] in valid]
    return kept, [c for c in claims if c["source_id"] not in valid]


def generate(question, chunks, num_ctx=8192, alias=True, max_claims=6, **kw):
    """Returns (claims_or_None, llm_stats). claims is None when the output was not valid JSON."""
    schema = {**CLAIMS_SCHEMA, "maxItems": max_claims}
    r = llm.chat(build_messages(question, chunks, alias=alias), schema=schema, num_ctx=num_ctx, **kw)
    claims = parse_claims(r["content"])
    return (unalias(claims, chunks) if claims is not None and alias else claims), r
