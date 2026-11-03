# docs/COST_FINOPS.md — Token Economics, INR/USD FinOps Telemetry & Caching

## 1. Gemini 2.5 & Multimodal Embedding Pricing Matrix

`CostTracker` (`src/insurance_mmrag/telemetry/cost_tracker.py`) tracks every API call at the exact token and image-tile level and reports costs in both **USD ($)** and **INR (₹)** (default conversion `USD_TO_INR_RATE = 84.0`, configurable via environment variables):

| Model Tier | Role in Pipeline | Input Cost (per 1M tokens) | Output Cost (per 1M tokens) | Image / Multimodal Cost |
| :--- | :--- | :--- | :--- | :--- |
| **`gemini-2.5-flash`** | Structure Analysis, Vision Table Parsing, Intent Routing, Standard Grounded Generation | `$0.15` (`₹12.60`) | `$0.60` (`₹50.40`) | `258 tokens` per image crop ($\approx \$0.000039$ / `₹0.0033` per table crop) |
| **`gemini-2.5-pro`** | Escalation for complex $\ge 3$-section cross-referenced legal synthesis | `$1.25` (`₹105.00`) | `$10.00` (`₹840.00`) | `258 tokens` per image crop |
| **`gemini-embedding-2-preview` / `001`** | Unified text, table & image embeddings | `$0.025` (`₹2.10`) | N/A | Included in token count |
| **`StubGeminiClient`** | Unit, Integration & Playwright E2E Testing | `$0.00` (`₹0.00` — simulated token telemetry verified separately) | `$0.00` | `$0.00` |

---

## 2. Three Architectural Cost-Control Mechanisms

### 2.1 Content-Addressable SHA-256 Disk Cache (`data/cache/`)
- **Vision Table Extraction Cache**: Before calling Gemini Vision on a cropped PDF table, `TableVisionParser` computes `sha256(crop_png_bytes + prompt_version)`. If present in `data/cache/tables/{sha256}.json`, the structured `ExtractedTableArtifact` is loaded from disk in $< 2\text{ms}$ at **`$0.00 / ₹0.00` API cost**.
- **Multimodal Embedding Cache**: Before embedding any `ChildChunk`, `MultimodalEmbedder` computes `sha256(model_name + embedding_input)`. Cached vectors in `data/cache/embeddings/` eliminate redundant embedding charges when re-indexing or updating metadata.

### 2.2 Tiered Model Routing (`Flash` by Default, `Pro` Only When Needed)
- $90\%+$ of insurance queries (single-section definitions, waiting periods, claim documents, or benefit table lookups) are answered by `gemini-2.5-flash` at $\sim 1/10\text{th}$ the cost and $3\times$ the speed of Pro.
- `gemini-2.5-pro` is selectively triggered by `IntentRouter` only when `requires_pro_escalation = True` ($\ge 3$ cross-referenced sections with conflicting provisos).

### 2.3 Hard Budget Circuit Breaker (`BudgetExceededError`)
- `CostTracker` enforces a configurable session and daily budget ceiling (`MAX_DAILY_BUDGET_USD = 5.00` / `₹420.00` by default).
- Before dispatching any non-cached LLM call, `CostTracker.check_budget()` verifies cumulative spend; if the ceiling is reached, it raises `BudgetExceededError` and logs a `FINOPS_BUDGET_CIRCUIT_BREAKER_TRIPPED` governance event.
