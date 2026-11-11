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

---

## Log Entry #008 — Phase 5 Context Assembly, Grounded Generation, Benchmark Scorecard, MCP & FastAPI
- **Timestamp**: `2026-11-04T09:30:00+05:30`
- **Observation**:
  1. Starlette/FastAPI `TestClient` methods (`.get()`, `.post()`) return partially dynamic types in strict Pyright unless explicitly cast or typed as `httpx.Client`. Casting `TestClient(app)` to `httpx.Client` ensures zero type warnings across all test suites.
  2. In PyMuPDF, inserting text via `page.insert_text((x, y), ...)` does not wrap long lines, which caused right-edge clipping on paragraphs and tables. Switching to `page.insert_textbox(rect, ...)` ensures automatic multi-line wrapping and preserves all factual numbers (such as `100% of Sum Insured` for AYUSH in-patient treatments).
  3. Cell tables extracted via `pymupdf.find_tables()` occasionally merge adjacent words without spaces (e.g. `CataractperEye`). Adding `_clean_cell` in the model stub and normalizing numbers in `BenchmarkRunner` prevents false negative numerical mismatch while retaining strict numerical exactness verification.
  4. Root waterfall execution spans (`pipeline.query` and `generation.grounded_synthesis`) must be populated into the response model upon outer context exit so the complete OpenTelemetry execution waterfall includes every phase from intent routing through synthesis.
- **Recursive Action Taken**:
  1. Updated `sample_policy_factory.py` to use `insert_textbox` with page-margin bounding boxes across all policy documents.
  2. Implemented `ContextAssembler` (parent promotion, 1-hop cross-reference expansion, CRAG sub-query hops), `GroundedGenerator` (calibrated confidence, $< 0.70$ abstention, citations), `MCPToolServer` (4 standard tools), `FastAPI` application (`/api/v1`), `CLI` (`mmrag`), and `BenchmarkRunner` (Quantitative RAG Triad Scorecard).
  3. Verified 63 unit and integration tests passing at 96.04% coverage with Ruff lint/format clean, Pyright 0 errors, Bandit SAST clean, and pre-commit passing.

---

## Log Entry #009 — Phase 6 Material Design 3 Web UI, Playwright E2E, Vitest & Streamlit Showcase
- **Timestamp**: `2026-11-04T09:47:00+05:30`
- **Observation**:
  1. Frontend TypeScript interfaces must strictly align with backend Pydantic models (e.g. `PrecedenceCheck.rule_applied` and `note` rather than dynamic fields) to prevent blank legal precedence banners.
  2. Playwright `webServer` automatically binds local port 8000 to launch Chromium E2E testing against FastAPI. In macOS sandbox environments, resolving `uv` to `/opt/homebrew/bin/uv` avoids shell execution permission traps.
  3. Prettier `--check` checks both `.ts` and `.css` files, requiring strict whitespace conformance across Material 3 stylesheets and test files.
  4. Streamlit and Jupyter notebook artifacts allow enterprise evaluators to choose between an interactive web application, an alternative rapid-prototyping dashboard (`streamlit run ui/streamlit_app.py`), or a self-contained visual execution notebook (`notebooks/Indian_Insurance_Multimodal_RAG_Showcase.ipynb`).
- **Recursive Action Taken**:
  1. Built Google Material Design 3 Web UI (`ui/web/index.html`, `material3.css`, `types.ts`, `api.ts`, `components.ts`, `main.ts`) featuring the 3-pane layout, execution trace waterfall, visual citation inspector, and confidence meters.
  2. Created 22 Vitest unit tests in `ui/web/src/__tests__/` achieving **99.62% line coverage** and 100% function coverage.
  3. Created 6 comprehensive Playwright E2E browser tests in `e2e/mmrag.spec.ts` passing 100% against Chromium.
  4. Created `ui/streamlit_app.py` dashboard and `notebooks/Indian_Insurance_Multimodal_RAG_Showcase.ipynb` notebook.
  5. Successfully verified all 10 ADLC quality gates (`npm run check`) exiting with code `0`.

---

## Log Entry #010 — Live Direct Provider Health Policy Ingestion & Unicode PII Edge Case
- **Timestamp**: `2026-11-04T14:40:00+05:30`
- **Observation**:
  1. Indian health insurance providers (HDFC ERGO, Tata AIG, Go Digit, Bajaj Allianz) publish official policy wordings PDFs directly on public CDN endpoints, ranging from 31 to 60 pages per document. Ingesting these documents directly via `httpx.Client(headers={"User-Agent": ...}, follow_redirects=True)` and validating with `PdfSanitizer` expands the corpus from 9 pages to 194 pages across 87 tables.
  2. In dense legal and grievance tables (e.g. Tata AIG MediCare Premier), grievance ombudsman phone listings contained Unicode en-dash escapes (`\u2013`) immediately followed by telephone digits (`011 \u2013 23213504`). The `PiiRedactor` Aadhaar regex (`(?<![\d+])\d{4}...`) matched `2013 2321 3504`, corrupting the Unicode escape into `\u[REDACTED_AADHAAR]`, causing downstream `json.decoder.JSONDecodeError: Invalid \uXXXX escape`.
  3. `StructureAnalyzer` and `table_vision_parser` extraction hints must pass `ensure_ascii=False` when dumping JSON so genuine Unicode characters (₹, –, etc.) remain native characters rather than backslash escape sequences.
  4. Both FastAPI (`/api/v1/policies`, `/api/v1/query`) and Streamlit (`ui/streamlit_app.py`) benefit from a manifest-driven architecture: discovering all downloaded policies from `manifest.json` on startup and performing lazy on-demand indexing upon query arrival keeps unit test suites running in <2 seconds while offering instant access to large multi-policy catalogs in production.
- **Recursive Action Taken**:
  1. Updated `scripts/fetch_irdai_policies.py` to download, sanitize, and register authentic health policies from HDFC ERGO (Optima Secure), Tata AIG (MediCare Premier), Go Digit (Health Plus), and Bajaj Allianz (Health Guard), updating `data/raw_policies/manifest.json`.
  2. Fixed `PiiRedactor` regex boundaries and ensured `ensure_ascii=False` across all prompt serialization.
  3. Upgraded `ui/streamlit_app.py` and `src/insurance_mmrag/api/main.py` with multi-policy selectors and lazy background ingestion.
  4. Re-verified all 10 quality gates passing 100%.

---

## Log Entry #011 — Retrieval Filter Blindness, Direct Answer Synthesis & Streamlit UX
- **Timestamp**: `2026-11-11T10:55:00+05:30`
- **Observation**:
  1. **Hard Section Filter Blindness**: In `HybridVectorStore`, applying `target_sections` as a hard `must` filter in Qdrant and a hard `continue` in BM25 blinded queries like *"is cataract surgery included or excluded"* when the intent router classified target sections as `[Base_Coverage, Exclusions, Definitions]`. Because cataract clauses are indexed under `Waiting_Periods` (Code-Excl02) and `Schedule_of_Benefits` (per-eye sub-limits), the hard filter blocked all relevant chunks, dropping confidence $< 0.70$ and triggering indeterminate abstention.
  2. **Generic Policy Text vs Direct Answers**: Previous stub generation echoed raw policy text chunks tagged with `[chk_...]` rather than providing an executive, direct answer to the user's question.
  3. **Streamlit UX Form Submission**: In `ui/streamlit_app.py`, standalone `st.text_input` and `st.button` required manual button clicking and did not submit on pressing the Enter key. In addition, sample query buttons required double clicks to execute.
- **Recursive Action Taken**:
  1. Updated `HybridVectorStore.search` to apply `target_sections` as a soft **Target Section Boost (+0.04)** in Reciprocal Rank Fusion (RRF), preserving strict filtering solely on `doc_id`.
  2. Enhanced `INTENT_CUES` in `irdai.py` so specific surgical procedures (cataract, hernia, hydrocele, piles, joint replacement) automatically target `WAITING_PERIODS` and `SCHEDULE_OF_BENEFITS` alongside `BASE_COVERAGE`.
  3. Upgraded `StubGeminiClient` to synthesize direct, natural language answers highlighting exact coverage status (`COVERED`, `COVERED_WITH_LIMITS`, `WAITING_PERIOD_APPLIES`, `EXCLUDED`), specific waiting periods, and monetary sub-limits before citing governing IRDAI clauses.
  4. Redesigned `ui/streamlit_app.py` with `st.form("insurance_query_form")` so pressing Enter immediately executes the query, added instant sample query execution, and placed a prominent **Direct Answer Card** above collapsible evidence citations and visual crops.
  5. Cleared stale LLM disk cache in `data/cache/llm` and verified all 10 ADLC quality gates (`npm run check`) passing 100% (65 pytest unit tests at 94.52% coverage, 22 vitest unit tests at 99.62% coverage, and 6/6 Playwright E2E tests).

---

## Log Entry #012 — V2 Phase 1: Provider Catalog Normalization & Family Floater Split Actuarial Math
- **Timestamp**: `2026-11-11T18:48:00+05:30`
- **Observation**:
  1. In Indian health insurance underwriting, Family Floater base premiums are anchored to the **eldest member's age band**. When a 26-year-old proposer adds parents aged 55–58 into a single 5-member floater, the entire 5-member pool is priced at the 56–60 age bracket (+300% rate jump), and any routine parent hospitalization resets the entire family's No-Claim Bonus.
  2. Ruff's `RUF001` rule flags Unicode en-dashes (`–`) in Python string literals as ambiguous characters; standardizing on ASCII hyphens (`-`) inside Python source strings avoids lint failures while maintaining clean formatting.
- **Recursive Action Taken**:
  1. Built `src/insurance_mmrag/domain/policy_catalog.py` normalizing all 6 policies in `manifest.json` into clause-cited `PolicyFeatureCard` objects.
  2. Built `src/insurance_mmrag/domain/premium_calculator.py` with age-band base rates, Sum Insured scaling, non-smoker/non-drinker healthy-lifestyle discounts (5%–7.5%), 18% GST, and `evaluate_portfolio_split()` comparing Single Floater vs. Split Portfolio (Young Nuclear Floater + Parent Floater).

---

## Log Entry #013 — V2 Phases 2 & 3: Probing Underwriter, Clause-Grounded Comparator & Claim Bill Simulator
- **Timestamp**: `2026-11-11T18:57:00+05:30`
- **Observation**:
  1. When a user asks *"I am individual with age 26, non smoker and non drinker with family of 5 what is the best policy for me"*, four underwriting slots determine whether a policy will succeed or fail at claim time: (a) whether the 5 members include senior parents vs. spouse/kids, (b) whether any member has a Pre-Existing Disease (`Excl01`), (c) the City Tier (which dictates hospital room rent per day), and (d) the priority between zero out-of-pocket deductions vs. lowest annual premium.
  2. Rather than blocking the user with an empty form, the optimal product pattern is **Immediate Value + Progressive Slot Probing**: provide an immediate ranked recommendation and family-split cost breakdown on Turn 1 alongside 4 interactive probing questions that dynamically re-rank the portfolio as the user answers them.
- **Recursive Action Taken**:
  1. Built `RecommendationEngine` (`src/insurance_mmrag/advisor/recommendation_engine.py`), `PolicyComparator` (`src/insurance_mmrag/advisor/policy_comparator.py`), and `ClaimSimulator` (`src/insurance_mmrag/advisor/claim_simulator.py`).
  2. Integrated advisory auto-detection into `InsuranceMMRAGPipeline.query()` so general queries asking for the best policy automatically return structured `advisor_recommendation` payloads.

---

## Log Entry #014 — V2 Phase 4: FastAPI Advisory & Comparison Endpoints, MCP Tools & CLI
- **Timestamp**: `2026-11-11T21:44:00+05:30`
- **Observation**:
  1. In strict Pyright, `isinstance(raw_ids, list)` narrows an `Any` or `object` dictionary value to `list[Unknown]`; explicitly casting via `cast(list[object], raw_ids)` before list comprehension preserves 0-error static type checking.
- **Recursive Action Taken**:
  1. Added `POST /api/v1/advisor/recommend`, `POST /api/v1/policies/compare`, and `POST /api/v1/policies/simulate-claim` to `src/insurance_mmrag/api/main.py`.
  2. Added `recommend_best_insurance_policy` and `compare_insurance_policies` MCP tools in `src/insurance_mmrag/mcp_tools.py` and `recommend`/`compare` subcommands in `src/insurance_mmrag/cli.py`.




  2. Tightened `PiiRedactor` Aadhaar regex lookbehind to `(?<![a-zA-Z\d\\+])`, ensuring escapes and variable identifiers are never falsely matched as Aadhaar numbers.
  3. Configured `table_vision_parser.py` to use `ensure_ascii=False` and added resilient escape-sequence recovery in `stub_gemini.py` `_parse_rows`.
  4. Updated `api/main.py` and `ui/streamlit_app.py` with dynamic manifest discovery and on-demand policy ingestion.
  5. Updated `e2e/mmrag.spec.ts` to assert flexible multi-policy dropdown options ($\ge 2$).
  6. Verified all 10 ADLC quality gates (`npm run check`) 100% green with 94.77% Python test coverage, 99.62% TypeScript test coverage, and 6/6 passing Playwright E2E tests.
