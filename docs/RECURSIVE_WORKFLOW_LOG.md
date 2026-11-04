# docs/RECURSIVE_WORKFLOW_LOG.md — Living Log of Discoveries & Plan Mutations

This file implements the **Recursive Workflow Planning** memory loop. Every time we uncover a domain nuance, document layout quirk, type-checking constraint, security edge case, or testing improvement, we log it here and propagate the rule into `docs/PLAN.md`, `docs/SPEC.md`, `docs/TESTING.md`, and `.agent/skills/indian-insurance-mmrag/SKILL.md`.

---

## Log Entry #001 — Initial Synthesis: Together AI (`ColQwen2`) vs. Indian Insurance Policies (IRDAI)
- **Timestamp**: `2026-11-03T22:20:00+05:30`
- **Observation**: The reference Together AI notebook (`MultiModal_RAG_with_Nvidia_Investor_Slide_Deck.ipynb`) uses `byaldi` + `vidore/colqwen2-v0.1` to embed whole PDF pages as image patches and pass top-$k$ page images to a Vision LLM. While effective for self-contained investor slides, Indian insurance policy wordings (50–80 pages of dense 8pt legal clauses with cross-section references between *Base Coverage*, *Waiting Periods `Excl01`–`Excl03`*, *Permanent Exclusions `Excl04`–`Excl18`*, and *Schedule of Benefits*) fail when only isolated page images are retrieved.
- **Recursive Action Taken**:
  1. Designed a hybrid architecture in `docs/ARCHITECTURE.md` combining **Parent-Child hierarchical text chunking + Cross-Reference Graph resolution** with **Gemini 2.5 Vision Table Extraction + high-DPI PNG visual crops**.
  2. Preserved the best feature of the Together AI notebook—passing the raw visual crop alongside the extracted Markdown table at generation time and displaying it in the UI's Right Visual Grounding Inspector.

---

## Log Entry #002 — ADLC Quality Gates, Cross-Platform Scripts & Stub-First Testing
- **Timestamp**: `2026-11-03T22:41:30+05:30`
- **Observation**: Standard Python-only test plans miss frontend TypeScript verification, browser E2E checks, pre-commit enforcement, and Windows compatibility (`package.json` scripts using bash-specific syntax break on Windows). Additionally, unit/integration tests that call live LLM APIs are flaky, slow, and incur unnecessary token cost.
- **Recursive Action Taken**:
  1. Updated `AGENTS.md`, `docs/PLAN.md`, and `docs/TESTING.md` so `uv sync` and `npm install` install everything including `.git/hooks/pre-commit`, `npm run dev` starts both backend and dashboard, and `npm run check` runs:
     - **Python**: `ruff` (lint + format), `pyright`, `bandit` (SAST), and `pytest` with $\ge 80\%$ coverage.
     - **TypeScript**: `ESLint`, `Prettier`, `tsc`, and `vitest` with $\ge 80\%$ coverage.
     - **End-to-End**: `Playwright` browser tests verifying the Google Material Design 3 UI.
  2. Enforced the **Stub Model Rule**: All automated tests use `StubGeminiClient` and never call a live external model.
  3. Enforced the **Cross-Platform Rule**: All `package.json` scripts use `uv run` or Node `.mjs` scripts so everything runs identically on Windows, macOS, and Linux.

---

## Log Entry #007 — Phase 4 Hybrid RRF Search, Table Ownership & Pyright Typings
- **Timestamp**: `2026-11-04T09:12:00+05:30`
- **Observation**: When adjacent sections share a page boundary, table artifacts must be assigned to exactly one section to prevent duplicate table child chunks from overwriting vector store payloads. In addition, `qdrant-client`'s modern `query_points` API returns strictly typed `QueryResponse.points`, and a local type stub for `rank_bm25` under `typings/` satisfies strict Pyright without disabling any type rules.
- **Recursive Action Taken**:
  1. Updated `StructureAnalyzer` with `assigned_tables` deduplication so each benefit table belongs to exactly one section.
  2. Implemented `HybridVectorStore` using `QdrantClient.query_points` and BM25Okapi with Reciprocal Rank Fusion (RRF), clause boosts (+0.05 for `Excl01`–`Excl18`), and table boosts (+0.02).
  3. Added `typings/rank_bm25/__init__.pyi` with `stubPath = "typings"` in `pyproject.toml`.
  4. Verified all 50 unit and integration tests at 97.18% coverage.
