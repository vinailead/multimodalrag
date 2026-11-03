# docs/TESTING.md — Quality Gates, Linting, Type-Checking, Coverage & E2E Matrix

## 1. Master Quality Gate Command (`npm run check`)

Running `npm run check` at the repository root invokes `node scripts/check.mjs`, a cross-platform (Windows, macOS, Linux) runner that executes every verification step in sequence and fails fast on any non-zero exit code:

| Gate # | Stack | Tool & Command | Enforcement Threshold / Rule |
| :--- | :--- | :--- | :--- |
| **1** | **Python Lint** | `uv run ruff check src/ tests/ scripts/` | Zero lint warnings/errors (`E`, `F`, `W`, `I`, `B`, `UP`, `SIM`, `RUF`, `S`). |
| **2** | **Python Format** | `uv run ruff format --check src/ tests/ scripts/` | 100% PEP8/Black-compatible formatting compliance. |
| **3** | **Python Typecheck** | `uv run pyright` | Strict static type checking (`typeCheckingMode = "strict"`), zero errors. |
| **4** | **Python Security (SAST)** | `uv run bandit -c pyproject.toml -r src/ scripts/` | Zero medium/high security vulnerabilities. |
| **5** | **Python Unit & API Tests** | `uv run pytest --cov=src/insurance_mmrag --cov-fail-under=80` | All tests pass using `StubGeminiClient` (never calls live LLM); coverage $\ge 80\%$ (targeting $\ge 85\%$). |
| **6** | **TypeScript Lint** | `npx eslint ui/web/src e2e` | Zero ESLint errors or warnings. |
| **7** | **TypeScript Format** | `npx prettier --check "ui/web/src/**/*.{ts,css,html}" "e2e/**/*.ts"` | 100% Prettier formatting compliance. |
| **8** | **TypeScript Typecheck** | `npx tsc --noEmit` | Strict TypeScript compiler check (`strict: true`, `noImplicitAny: true`). |
| **9** | **TypeScript Unit Tests** | `npx vitest run --coverage` | All frontend unit tests pass; coverage $\ge 80\%$ (lines, functions, statements). |
| **10** | **Playwright E2E Tests** | `npx playwright test` | Full browser end-to-end tests against FastAPI + Google Material Design 3 UI pass 100%. |

---

## 2. Git Pre-Commit Hook (`.git/hooks/pre-commit`)

- Installed automatically when running `npm install` via the `"prepare": "node scripts/install-hooks.mjs"` lifecycle script in `package.json`.
- Invokes `node scripts/pre-commit.mjs` on every `git commit`.
- Runs format (`ruff format --check` + `prettier --check`), lint (`ruff check` + `eslint`), static type checks (`pyright` + `tsc --noEmit`), security (`bandit`), and unit tests (`pytest` + `vitest run`).
- **Rule**: `git commit --no-verify` is strictly forbidden.

---

## 3. Stub Model Architecture (`StubGeminiClient`)

Per `AGENTS.md`: **Tests never call a live model; use a stub model.**
- `src/insurance_mmrag/testing/stub_gemini.py` implements the exact `GeminiClientProtocol` interface used by `StructureAnalyzer`, `TableVisionParser`, `MultimodalEmbedder`, `IntentRouter`, and `GroundedGenerator`.
- Produces deterministic, domain-accurate responses for IRDAI policy sections, multi-header benefit tables, 768-d L2-normalized semantic embeddings, intent classifications, and grounded citations.
- Simulates token counts (`prompt_tokens`, `completion_tokens`, `embedding_tokens`) so `CostTracker` arithmetic and `BudgetExceededError` circuit breakers are rigorously tested without spending API credits.

---

## 4. Cross-Platform Compatibility (Windows, macOS, Linux)

- All `package.json` scripts use either `uv run ...` or `node scripts/*.mjs`.
- Path manipulation in both Python (`pathlib.Path`) and Node (`node:path`) uses OS-agnostic joins and forward-slash normalization for URLs and metadata IDs.
