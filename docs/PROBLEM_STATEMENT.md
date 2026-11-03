# docs/PROBLEM_STATEMENT.md — Indian Insurance Policy Multimodal RAG

## 1. Executive Summary

Standard Retrieval-Augmented Generation (RAG) pipelines—including pure fixed-window text chunkers and pure single-page image retrievers (like naive `ColPali`/`ColQwen2` pipelines)—fail systematically when applied to **Indian Insurance Policy Wordings and Customer Information Sheets (CIS)** regulated by the **Insurance Regulatory and Development Authority of India (IRDAI)**.

Policyholders, claims adjusters, underwriters, and insurance advisors asking seemingly simple questions—such as *"Is robotic knee replacement covered under my ₹5 Lakh policy after 18 months, and what will my out-of-pocket room rent deduction be?"*—require simultaneous synthesis across **multiple non-adjacent sections**, **defined legal terms**, **IRDAI standard exclusion codes (`Excl01`–`Excl18`)**, and **complex multi-header tabular schedules**.

---

## 2. Four Structural Failure Modes of Traditional RAG on Indian Insurance Policies

### Failure Mode 1: Non-Linear Cross-Referencing & Context Severing
Indian health, motor, and life insurance policies are drafted as interconnected legal state machines:
- **Section B (Base Coverage)** states that *In-Patient Hospitalization* and *Modern Treatment Methods* are covered up to the Sum Insured.
- **Section C (Waiting Periods)** restricts coverage via:
  - `Excl03`: 30-Day Initial Waiting Period (except accidents)
  - `Excl02`: 24-Month Specified Disease/Procedure Waiting Period (e.g., Cataract, Joint Replacement, Hernia, Renal Stones)
  - `Excl01`: 36-Month (or 48-Month) Pre-Existing Disease (PED) Waiting Period
- **Section D (Permanent Exclusions)** lists IRDAI Standard Exclusion codes (`Excl04` through `Excl18`, such as Cosmetic Surgery, Obesity/Weight Control, Unproven Treatments, Maternity unless rider attached).
- **Section E (Cost Sharing / Proportionate Deduction)** stipulates that if the insured occupies a hospital room category exceeding the eligible **Room Rent Limit** (e.g., $1\%$ of Sum Insured per day), **all associated medical expenses** (surgeon fees, anesthesia, OT charges) are reduced proportionately.

When a naive chunker splits a PDF into 500-token chunks, the chunk containing *"In-Patient Hospitalization is covered up to 100% of Sum Insured"* is retrieved in isolation without its modifying waiting period (`Excl02`) or proportionate deduction proviso, leading to **dangerous coverage hallucinations**.

### Failure Mode 2: Destruction of Multi-Header Tabular Schedules & CIS Layouts
Every Indian insurance policy includes a **Customer Information Sheet (CIS)** and a **Schedule of Benefits**:
- Tables feature merged super-headers (e.g., *Plan Variants: Silver / Gold / Platinum* or *Sum Insured Slabs: ₹3L / ₹5L / ₹10L / ₹25L*), nested sub-limits (e.g., *Cataract: up to 25% of SI or ₹40,000 per eye, whichever is lower*), and critical footnote markers (`*`, `**`, `†`).
- Standard PDF text extractors (`pypdf`, `pdfminer`) flatten table cells out of order, losing row-to-column alignment and stripping visual footnotes.
- Pure page-image retrieval (`ColQwen2`) captures the visual page but lacks fine-grained clause-level semantic indexing and cannot automatically expand cross-referenced definitions from 15 pages earlier.

### Failure Mode 3: Semantic Interference Between Coverage and Exclusion Clauses
Because *Coverage* clauses and *Exclusion* clauses share almost identical vocabulary (e.g., *"hospitalization"*, *"surgical procedure"*, *"maternity"*, *"pre-existing disease"*), an unfiltered vector search for *"deductible and room rent co-payment"* frequently retrieves dozens of unrelated exclusion clauses, crowding out the actual *Cost Sharing* and *Schedule of Benefits* sections.

### Failure Mode 4: Lack of Calibrated Abstention & Regulatory Grounding
In regulated financial and insurance products under IRDAI Protection of Policyholders' Interests Regulations, guessing an answer when a policy document does not specify a benefit is unacceptable. Traditional RAG systems generate plausible-sounding answers even when retrieval confidence is low, and fail to provide verifiable **Page Number + Section Type + IRDAI Clause Code + Visual Table/Page Crop** citations.

---

## 3. Target Solution Architecture

Our **Indian Insurance Multimodal RAG System** solves all four failure modes by combining:
1. **Pre-Chunking IRDAI Structural Analysis**: Classifying document regions into 9 canonical IRDAI functional section types before chunking.
2. **Parent-Child Hierarchical Chunking + Cross-Reference Graph Resolution**: Indexing atomic **Child Chunks** for high-precision vector/lexical matching while retrieving complete **Parent Sections** and automatically resolving linked `Excl01`–`Excl18` and defined-term references.
3. **Gemini 2.5 Vision Table Extraction & Enrichment**: Cropping tables as high-DPI PNG snapshots, extracting structured Markdown/JSON via Vision LLM, and generating synthetic Q&A pairs while preserving the raw visual image for side-by-side verification.
4. **Hybrid Multimodal Indexing (`gemini-embedding-2` + Qdrant + BM25 RRF)**: Combining dense multimodal embeddings with exact lexical BM25 matching for IRDAI codes (`UIN`, `Excl01`, clause numbers).
5. **Pre-Retrieval Intent Routing**: Filtering vector search by predicted `SectionType` tags before retrieval.
6. **Grounded Generation with Deterministic Abstention ($<0.70$), DPDP Act 2023 PII Redaction, and Live USD/INR FinOps Telemetry**.
