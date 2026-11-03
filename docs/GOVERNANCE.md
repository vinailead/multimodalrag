# docs/GOVERNANCE.md — IRDAI Regulatory Compliance, Abstention & Audit Trail

## 1. Regulatory Context (IRDAI Protection of Policyholders' Interests Regulations)

Insurance policy interpretation in India is governed by the **Insurance Regulatory and Development Authority of India (IRDAI)**:
- Standard Health Insurance definitions and exclusion codes (`Excl01`–`Excl18`) must be cited verbatim without distortion.
- **Customer Information Sheets (CIS)** provide a summary, but in any legal interpretation, the full **Policy Wordings** and **Schedule of Benefits** govern. Our Parent-Child + Cross-Reference architecture ensures that summary hits are always cross-checked against full section clauses.
- **Zero-Hallucination Mandate**: A system must never fabricate coverage limits, waiting periods, or claim eligibility when the underlying policy evidence is missing or ambiguous.

---

## 2. Calibrated Confidence Scoring & Deterministic Abstention (`< 0.70`)

Every response computes a composite confidence score $C \in [0.0, 1.0]$:
$$C = 0.45 \cdot S_{\text{retrieval\_rrf}} + 0.35 \cdot S_{\text{llm\_self\_grounding}} + 0.20 \cdot S_{\text{citation\_alignment}}$$

Where:
- $S_{\text{retrieval\_rrf}}$: Normalized Reciprocal Rank Fusion score of the top retrieved child chunks within the intent-filtered section scope.
- $S_{\text{llm\_self\_grounding}}$: Grounding score returned by the structured generation schema based on whether every aspect of the user's question is explicitly addressed in the assembled parent chunks.
- $S_{\text{citation\_alignment}}$: Verification that every returned `GroundedCitation` points to a valid `parent_id`, `page_number`, and non-empty `verbatim_quote` present in the indexed document.

### Mandatory Abstention Rule
If $C < 0.70$ (configurable via `MIN_CONFIDENCE_THRESHOLD=0.70`), `GroundedGenerator` overrides any speculative answer, sets `abstained = True`, sets `coverage_summary.coverage_status = "INDETERMINATE"`, and outputs:
> *"INDETERMINATE COVERAGE (Confidence below 0.70 threshold): The indexed IRDAI policy document does not contain sufficient verifiable clauses to deterministically confirm coverage, sub-limits, or exclusions for this query. Please refer to the full Policy Schedule or contact the insurer's underwriting/claims desk."*

---

## 3. Tamper-Evident Hash-Chained Audit Log (`src/insurance_mmrag/telemetry/audit_logger.py`)

Every ingestion and query event appends an immutable JSON record to `logs/audit_trail.jsonl`. Each record includes a `prev_hash` and `record_hash` (SHA-256 over the canonical JSON + `prev_hash`), creating a verifiable cryptographic chain:

```json
{
  "timestamp": "2026-11-03T17:10:00Z",
  "event_type": "POLICY_QUERY",
  "query_id": "qry_8f92a1c4",
  "redacted_query": "What is the waiting period for cataract surgery under [REDACTED_POLICY_ID]?",
  "pii_redactions": ["POLICY_ID"],
  "intent_sections": ["Waiting_Periods", "Schedule_of_Benefits", "Exclusions"],
  "retrieved_child_ids": ["chk_14_02", "chk_04_table_qa3"],
  "assembled_parent_ids": ["par_waiting_periods_03", "par_schedule_01", "par_def_ped"],
  "model_used": "gemini-2.5-flash",
  "confidence_score": 0.91,
  "abstained": false,
  "cost_usd": 0.00042,
  "cost_inr": 0.03528,
  "latency_ms": 142.5,
  "prev_hash": "a4f0...91b2",
  "record_hash": "e7c9...34d8"
}
```
