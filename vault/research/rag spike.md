# rag spike

Full write-up: `docs/RAG_SPIKE.md`. Reproduce: `python scripts/rag_spike.py --all`. Code: [[ingest]], [[retrieve]].

**Verdict:** the design works on the real HPE manuals on this laptop (2026-10-17).

- 3,777 chunks from 7 manuals; GPU embed 167 s; embeddinggemma dim 768 matches the schema.
- Hybrid (vector + idf keyword, RRF) + subsystem filter: recall@5 0.81, MRR 0.74 on 27 questions; 0% wrong-subsystem rows.
  Unfiltered: 10% (vector) to 27% (keyword) of top-5 rows came from the wrong subsystem.
- Qwen `qwen3.5:4b`: 100% valid JSON, 100% cited ids valid (with S1..Sn aliases), ~48 tok/s, 3.1 GiB VRAM, 100% GPU, p50 3.8 s.
- MiniCheck-Flan-T5-Large on CPU: separates 12 supported vs 12 unsupported claims perfectly, 1.3 s/claim. Keep it.
- Prompt-based sufficiency gate: 10/10 (weak evidence: unanswerable items were easy).
- Risks: tiny eval sets; exact `version_id` match breaks multi-series manuals; L-series unknown; text extraction artifacts.
