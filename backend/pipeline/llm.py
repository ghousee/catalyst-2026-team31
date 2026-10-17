"""Thin Ollama chat client with structured output and timing/VRAM stats (shared by generate.py and gate.py)."""
import time

import httpx

from backend import settings


def chat(messages, schema=None, num_ctx=8192, temperature=0.0, max_tokens=700, think=False,
         url=None, model=None, timeout=600):
    """One non-streaming /api/chat call. Returns {"content", "seconds", "prompt_tokens", "gen_tokens", "tok_per_s"}.

    `schema` is a JSON schema passed as Ollama's `format` (constrained decoding).
    think=False disables Qwen3.x thinking tokens (they would eat the budget and the latency).
    """
    url, model = url or settings.OLLAMA_URL, model or settings.LLM_MODEL
    body = {"model": model, "messages": messages, "stream": False, "think": think,
            "options": {"num_ctx": num_ctx, "temperature": temperature, "num_predict": max_tokens}}
    if schema is not None:
        body["format"] = schema
    t0 = time.time()
    r = httpx.post(f"{url}/api/chat", json=body, timeout=timeout)
    r.raise_for_status()
    j = r.json()
    dt = time.time() - t0
    gen = j.get("eval_count", 0)
    return {"content": j["message"]["content"], "seconds": dt, "prompt_tokens": j.get("prompt_eval_count", 0),
            "gen_tokens": gen, "tok_per_s": gen / (j["eval_duration"] / 1e9) if j.get("eval_duration") else 0.0}


def loaded_models(url=None):
    """/api/ps entries (name, size, size_vram, context_length) for what Ollama currently holds in memory."""
    r = httpx.get(f"{url or settings.OLLAMA_URL}/api/ps", timeout=30)
    r.raise_for_status()
    return r.json().get("models", [])
