# Pipeline modules (build in this order)
1. `context.py`   — extract entities (aliases table + LLM fallback) → {system, version, site, confidence}; ambiguous → clarify
2. `retrieve.py`  — deterministic graph query first; else pgvector search WHERE system/version/site match + ACL
3. `gate.py`      — sufficiency check (prompt to Qwen or Jev yes/no) → refer if insufficient
4. `generate.py`  — Qwen → JSON [{claim, source_id}] from retrieved items only; drop claims w/o valid source_id
5. `verify.py`    — MiniCheck(claim, source_text) → keep if score >= VERIFY_THRESHOLD
6. `experts.py`   — rank people via edge(expert_in) weights + active flag
7. `answer.py`    — assemble response per docs/API_CONTRACT.md; write answer_log
Each step must be toggleable via `ablation` (1 plain RAG … 4 full) for the eval.
