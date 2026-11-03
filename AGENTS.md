# AGENTS.md — Agentic Development Lifecycle (ADLC) & Process Charter

This repository implements a production-grade **Indian Insurance Policy Multimodal RAG System** governed by strict engineering, testing, security, FinOps, and recursive workflow planning rules.

---

## Process

`uv sync` and `npm install` at the repo root install everything, including a git pre-commit hook. `npm run dev` starts the FastAPI backend and the Google Material Design 3 TypeScript dashboard.

`npm run check` runs every check (via cross-platform `.mjs` and `uv run` scripts):

- **Python**:
  - `ruff check` (lint — PEP8, pyflakes, bugbear, simplify, security `S`, isort)
  - `ruff format --check` (formatting verification)
  - `pyright` (strict static type-checking across `src/`, `tests/`, and `scripts/`)
  - `bandit` (Static Application Security Testing / SAST scan on `src/` and `scripts/`)
  - `pytest` with **$\ge 80\%$ coverage** (`--cov=src/insurance_mmrag --cov-fail-under=80`, targeting $\ge 85\%$)
- **TypeScript / Web UI**:
  - `ESLint` (strict TypeScript + accessibility rules)
  - `Prettier` (`--check` formatting verification)
  - `tsc --noEmit` (strict TypeScript compiler verification)
  - `vitest` with **$\ge 80\%$ coverage** (`vitest run --coverage`, targeting $\ge 85\%$)
- **End-to-End Browser Verification**:
  - `Playwright` end-to-end tests (`npx playwright test`) against the running FastAPI + Google Material Design 3 Web UI

The **git pre-commit hook** (installed automatically in `.git/hooks/pre-commit` via `scripts/install-hooks.mjs` during `npm install`) runs the format, lint, type (`pyright` + `tsc`), security (`bandit`), and unit test (`pytest` + `vitest`) checks on every commit.

---

## Planning

When asked to plan, as in *"Please plan the pilot"*, write the plan to `docs/PLAN.md` and write **no code**.

- Split the work into **6 phases**, each building on the last.
- Give each phase detailed success criteria that you can verify yourself:
  - Tests that pass (`pytest`, `vitest`, `playwright`)
  - Commands and their expected output (`uv run ...`, `npm run ...`)
  - API calls and their expected JSON responses (`GET /api/v1/health`, `POST /api/v1/query`, `GET /api/v1/telemetry/cost`, etc.)
  - Pages and UI elements checked in the browser with Playwright / Chrome DevTools MCP
- Write each criterion as a markdown checkbox (`- [ ]`).
- Then **stop and wait** until you are asked to implement the plan.

---

## Implementing

When asked to implement the plan, as in *"Please implement the plan"*, build every phase in order without stopping. For each phase:

1. **Build it, with tests** (Python unit/integration tests in `tests/` + TypeScript unit tests in `ui/web/src/__tests__/` + Playwright E2E tests in `e2e/`).
2. **Check every success criterion** and fix whatever fails.
3. **Execute Recursive Workflow Planning**:
   - Whenever you discover a new edge case (e.g., IRDAI PDF multi-page table layout quirk, clause cross-reference pattern, type-checking subtlety, or cost optimization), immediately log it in `docs/RECURSIVE_WORKFLOW_LOG.md` and update `docs/PLAN.md`, `docs/SPEC.md`, and `.agent/skills/indian-insurance-mmrag/SKILL.md`.
4. **Tick off its criteria** (`- [x]`) in `docs/PLAN.md` and update `docs/STATUS.md`.
5. **Commit**: Run `git commit`. The pre-commit hook runs the checks automatically; if it fails, fix the root cause and commit again.

When the last phase is done, run `npm run check` and report the full results.

---

## Rules (Non-Negotiable Guardrails)

1. **Add tests with each change.** Tests never call a live external model (`google-genai`); always use the deterministic `StubGeminiClient` in unit, integration, and Playwright E2E tests. (Live Gemini API calls are strictly isolated to explicit CLI/script ingestion or benchmark runs when `GEMINI_API_KEY` is provided.)
2. **Outside a plan, commit each change once you have checked it.**
3. **Run `npm run check` before you hand work over.**
4. **Never use `git commit --no-verify`.**
5. **Never lower a threshold, turn off a rule, `# type: ignore`, `eslint-disable`, or exclude a file to get a green run.** If a rule looks wrong, stop and ask the user.
6. **Keep `docs/STATUS.md` and `docs/RECURSIVE_WORKFLOW_LOG.md` up to date** at the end of every phase.
7. **Never push (`git push` is strictly prohibited).**
8. **Don't open `data/evals/` unless you are explicitly asked to.**
9. **Cross-Platform Guarantee (Windows, macOS, Linux)**: Everything must work on Windows as well as macOS/Linux. Write all `package.json` scripts as `uv run` commands or cross-platform Node `.mjs` scripts (`node scripts/check.mjs`, `node scripts/dev.mjs`, `node scripts/install-hooks.mjs`). Never use bash-only syntax (`&&`, `rm -rf`, `export VAR=val`,chmod-only hooks) inside `package.json` scripts.
10. **Zero Generalization on Cost, Security, and Governance**:
    - Every LLM/embedding operation must pass through `PiiRedactor` (DPDP Act 2023 Aadhaar/PAN/Policy/Mobile masking) and `PdfSanitizer` (indirect prompt injection check).
    - Every operation must record token counts and USD/INR cost in `CostTracker` and write an immutable audit entry in `AuditLogger` (`logs/audit_trail.jsonl`).
    - Any query with grounded confidence $< 0.70$ must deterministically abstain with an IRDAI-compliant coverage disclaimer.
