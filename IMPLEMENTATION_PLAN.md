# Master ADLC Index & Implementation Plan — Indian Insurance Multimodal RAG

All ADLC planning, architectural specifications, security/governance charters, FinOps telemetry models, and testing quality gates are saved directly in your workspace `/Users/vinoth/project/multimodalrag/`:

---

## 1. Saved ADLC Markdown Files in `/Users/vinoth/project/multimodalrag/`

| Document | Path | Purpose |
| :--- | :--- | :--- |
| **Agent Charter & Rules** | [AGENTS.md](file:///Users/vinoth/project/multimodalrag/AGENTS.md) | `# Process`, `## Planning`, `## Implementing`, `## Rules` (`uv sync`, `npm install`, `npm run dev`, `npm run check`, pre-commit hook, stub models, Windows compatibility) |
| **6-Phase Plan & Checkboxes** | [docs/PLAN.md](file:///Users/vinoth/project/multimodalrag/docs/PLAN.md) | Detailed 6-phase plan with self-verifiable `- [ ]` checkboxes for unit tests, CLI outputs, API JSON payloads, and Playwright browser checks |
| **Project Status Tracker** | [docs/STATUS.md](file:///Users/vinoth/project/multimodalrag/docs/STATUS.md) | Live phase completion tracker maintained after each phase |
| **Problem Statement** | [docs/PROBLEM_STATEMENT.md](file:///Users/vinoth/project/multimodalrag/docs/PROBLEM_STATEMENT.md) | IRDAI regulatory nuances, non-linear cross-references (`Excl01`–`Excl18`), multi-header CIS/Benefit tables, and naive RAG failure analysis |
| **Technical Spec** | [docs/SPEC.md](file:///Users/vinoth/project/multimodalrag/docs/SPEC.md) | Gemini 2.5 Flash/Pro + Embedding 2 config, 9 IRDAI `SectionType` enums, Pydantic v2 schemas, and FastAPI REST endpoints |
| **Architecture & Elements** | [docs/ARCHITECTURE.md](file:///Users/vinoth/project/multimodalrag/docs/ARCHITECTURE.md) | Deep dive into the 6 core Multimodal RAG modules (Structure Analysis, Parent-Child + Cross-Ref Graph, Vision Table Extractor, Hybrid Qdrant+BM25 RRF, Intent Router, Grounded Generator) |
| **Google Design System** | [docs/DESIGN_SYSTEM.md](file:///Users/vinoth/project/multimodalrag/docs/DESIGN_SYSTEM.md) | Google Material Design 3 (M3) color tokens, typography (`Google Sans`, `Roboto`, `Roboto Mono`), and 3-pane workspace layout |
| **Security & DPDP Act 2023** | [docs/SECURITY.md](file:///Users/vinoth/project/multimodalrag/docs/SECURITY.md) | Aadhaar/PAN/Mobile/Policy PII masking, PDF indirect prompt-injection defense, SAST (`bandit`), and lockfile verification |
| **Governance & IRDAI** | [docs/GOVERNANCE.md](file:///Users/vinoth/project/multimodalrag/docs/GOVERNANCE.md) | Calibrated confidence scoring, deterministic abstention (`< 0.70`), and tamper-evident SHA-256 hash-chained `logs/audit_trail.jsonl` |
| **Cost & FinOps** | [docs/COST_FINOPS.md](file:///Users/vinoth/project/multimodalrag/docs/COST_FINOPS.md) | Exact USD ($) and INR (₹) token & image-tile accounting, SHA-256 content-addressable disk cache, and budget circuit breaker |
| **Testing & Quality Gates** | [docs/TESTING.md](file:///Users/vinoth/project/multimodalrag/docs/TESTING.md) | Full `npm run check` matrix: Python (`ruff`, `pyright`, `bandit`, `pytest >=80% cov`), TypeScript (`eslint`, `prettier`, `tsc`, `vitest >=80% cov`), and `Playwright` E2E |
| **Recursive Workflow Log** | [docs/RECURSIVE_WORKFLOW_LOG.md](file:///Users/vinoth/project/multimodalrag/docs/RECURSIVE_WORKFLOW_LOG.md) | Living engineering memory that records every edge case discovered and mutates `docs/PLAN.md` & `SKILL.md` |
| **Reusable Agent Skill** | [.agent/skills/indian-insurance-mmrag/SKILL.md](file:///Users/vinoth/project/multimodalrag/.agent/skills/indian-insurance-mmrag/SKILL.md) | Portable Antigravity Skill packaging the Indian Insurance Multimodal RAG architecture and rules |

---

## 2. Summary of the Quality Gates (`npm run check`)

- **`uv sync` and `npm install`** at the repo root install all Python and TypeScript dependencies plus the automatic git pre-commit hook (`.git/hooks/pre-commit`).
- **`npm run dev`** starts the FastAPI backend and the Google Material Design 3 TypeScript dashboard via cross-platform `node scripts/dev.mjs`.
- **`npm run check`** runs every gate via cross-platform `node scripts/check.mjs`:
  1. **Python**: `uv run ruff check`, `uv run ruff format --check`, `uv run pyright`, `uv run bandit`, and `uv run pytest` with $\ge 80\%$ coverage (using `StubGeminiClient` — tests never call a live model).
  2. **TypeScript**: `ESLint`, `Prettier --check`, `tsc --noEmit`, and `vitest run --coverage` with $\ge 80\%$ coverage.
  3. **Browser E2E**: `Playwright` end-to-end tests (`npx playwright test`) verifying the live Google Material Design 3 Web UI, citations, visual table crops, confidence badges, abstention banner, and FinOps/PII telemetry.
