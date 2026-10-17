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


def label(i, alias):
    return f"S{i + 1}" if alias else None


def build_messages(question, chunks, max_chars=3500, alias=True):
    """chunks: [{id, text}]. Each source is truncated to max_chars to bound the prompt.

    alias=True labels sources S1..Sn instead of their long ids (the model copies short labels reliably;
    with raw ids it invented ids derived from message numbers inside merged chunks). Use unalias() after.
    """
    src = "\n\n".join(f"[source_id: {label(i, alias) or c['id']}]\n{c['text'][:max_chars]}"
                     for i, c in enumerate(chunks))
    return [{"role": "system", "content": SYSTEM},
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


def generate(question, chunks, num_ctx=8192, alias=True, **kw):
    """Returns (claims_or_None, llm_stats). claims is None when the output was not valid JSON."""
    r = llm.chat(build_messages(question, chunks, alias=alias), schema=CLAIMS_SCHEMA, num_ctx=num_ctx, **kw)
    claims = parse_claims(r["content"])
    return (unalias(claims, chunks) if claims is not None and alias else claims), r
