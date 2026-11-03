---
name: indian-insurance-mmrag
description: End-to-end architecture, IRDAI domain taxonomy, parent-child chunking, Gemini 2.5 Vision table extraction, DPDP Act 2023 PII redaction, USD/INR FinOps tracking, and ADLC quality gates for Indian Insurance Policy Multimodal RAG systems.
---

# Indian Insurance Policy Multimodal RAG Skill (`indian-insurance-mmrag`)

Use this skill whenever building, extending, auditing, or evaluating Multimodal RAG pipelines over **Indian Insurance Policy Wordings, Customer Information Sheets (CIS), and Benefit Schedules** regulated by IRDAI.

---

## 1. Mandatory IRDAI Domain Taxonomy (`SectionType`)

Never use generic fixed-window chunking on Indian insurance PDFs. Always run a **Pre-Chunking Structure Analysis Pass** that maps document sections to these 9 canonical categories:
1. `CIS_Summary` — Customer Information Sheet (Key policy snapshot)
2. `Schedule_of_Benefits` — Plan tiers, Sum Insured slabs, Room Rent limits, Sub-limits
3. `Definitions` — IRDAI Standard Definitions & Policy-Specific Definitions
4. `Base_Coverage` — In-patient hospitalization, Day care, AYUSH, Domiciliary, Restore benefit
5. `Optional_Riders` — Add-on covers, Maternity, OPD, Critical Illness, Consumables
6. `Waiting_Periods` — Initial 30-day (`Excl03`), 24-month Specified Diseases (`Excl02`), 36/48-month Pre-Existing Diseases (`Excl01`)
7. `Exclusions` — Standard Permanent Exclusions (`Excl04`–`Excl18`) and Specific Exclusions
8. `Cost_Sharing` — Deductibles, Co-payments, Room Rent / ICU Proportionate Deduction clauses
9. `Claims_and_Grievance` — Cashless/Reimbursement notice timelines, documents, Bima Bharosa / Insurance Ombudsman

---

## 2. Core Pipeline Rules

1. **Parent-Child + Cross-Reference Graph**:
   - Index atomic clauses and synthetic table Q&As as `ChildChunk`s (`80–250` tokens).
   - Store complete sections as `ParentChunk`s (`600–2500` tokens).
   - Resolve references to `Excl01`–`Excl18`, section numbers, and defined terms into `metadata.cross_references` so 1-hop linked parents are automatically assembled at query time.
2. **Vision Table Extraction + Raw Visual Crop**:
   - Render table bounding boxes at 200 DPI to PNG (`data/cache/crops/`).
   - Extract structured Markdown, JSON rows, footnotes, title, summary, and 5+ synthetic Q&As via Gemini Vision (`gemini-2.5-flash`).
   - Pass **both** the Markdown table and the PNG crop to the generator and UI citation inspector.
3. **Security, FinOps & Governance**:
   - Mask Aadhaar, PAN, Mobile, Email, and Policy IDs via `PiiRedactor` (DPDP Act 2023) before any LLM/embedding call.
   - Cache Vision table extractions and embeddings by SHA-256 content hash (`data/cache/`).
   - Track exact USD and INR costs in `CostTracker` and log hash-chained records to `logs/audit_trail.jsonl`.
   - Enforce deterministic abstention (`abstained = True`) whenever grounded confidence $< 0.70$.
4. **ADLC Quality Gate (`npm run check`)**:
   - Tests must use `StubGeminiClient` and never call a live model.
   - `npm run check` must pass Python (`ruff`, `pyright`, `bandit`, `pytest` $\ge 80\%$ cov), TypeScript (`eslint`, `prettier`, `tsc`, `vitest` $\ge 80\%$ cov), and `Playwright` E2E checks before handing work over.
   - Log every new edge case in `docs/RECURSIVE_WORKFLOW_LOG.md`.
