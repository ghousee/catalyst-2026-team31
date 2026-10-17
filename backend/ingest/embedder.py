"""Ollama embeddings (embeddinggemma). Task prefixes follow the model card:
documents: "title: <title> | text: <body>", queries: "task: search result | query: <q>".

Bulk ingest may run on the GPU (fast, one-off); the runtime query path should use cpu=True so the
LLM keeps the VRAM (CLAUDE.md stack).
"""
import httpx

from backend import settings


def doc_text(section, body):
    return f"title: {section or 'none'} | text: {body}"


def query_text(q):
    return f"task: search result | query: {q}"


def embed(texts, cpu=False, batch=16, url=None, model=None, timeout=900):
    """Embed texts; returns (vectors, prompt_tokens). Order preserved."""
    url, model = url or settings.OLLAMA_URL, model or settings.EMBED_MODEL
    opts = {"num_gpu": 0} if cpu else {}
    vecs, toks = [], 0
    for i in range(0, len(texts), batch):
        r = httpx.post(f"{url}/api/embed", timeout=timeout,
                       json={"model": model, "input": texts[i:i + batch], "options": opts, "keep_alive": "60m"})
        r.raise_for_status()
        j = r.json()
        vecs.extend(j["embeddings"])
        toks += j.get("prompt_eval_count", 0)
    return vecs, toks


def embed_query(q, cpu=True, **kw):
    return embed([query_text(q)], cpu=cpu, **kw)[0][0]
