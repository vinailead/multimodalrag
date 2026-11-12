# docs/SPEC.md — Technical Specification, Schemas & API Contracts

## 1. AI & Storage Stack

| Layer | Technology | Configuration & Rationale |
| :--- | :--- | :--- |
| **Multimodal SDK** | `google-genai` (official Google GenAI Python SDK) | Unified client for Gemini 2.5 Vision, structured outputs, and embeddings. |
| **Fast Vision & Structured Tasks** | `gemini-2.5-flash` | Used for Pre-Chunking Structure Analysis, Vision Table Extraction + Q&A generation, Pre-Retrieval Intent Routing, and standard Grounded Generation. |
| **Complex Legal Escalation Model** | `gemini-2.5-pro` | Automatically invoked when assembled context spans $\ge 3$ distinct cross-referenced policy sections or complex multi-clause exclusions. |
| **Multimodal Embedding Model** | `gemini-embedding-2-preview` (with fallback to `gemini-embedding-001`) | 768-dimensional L2-normalized embeddings across text clauses, enriched tables, and visual crops. |
| **Test Stub Model** | `StubGeminiClient` | Deterministic offline model stub used in 100% of automated unit, integration, and Playwright E2E tests. |
| **Hybrid Vector Store** | Local `qdrant-client` + `rank-bm25` | Combines dense cosine similarity with sparse BM25 lexical scoring via Reciprocal Rank Fusion ($k=60$). |
| **Backend API** | FastAPI + Pydantic v2 + Uvicorn | Strictly typed async REST API with OpenAPI 3.1 schema generation. |
| **Web Frontend** | TypeScript + Vite + Google Material Design 3 | Zero-runtime-bloat M3 interface tested with ESLint, Prettier, `tsc`, Vitest, and Playwright. |

---

## 2. Canonical IRDAI Section Taxonomy (`SectionType`)

Every parsed block, parent chunk, and child chunk is tagged with one of 9 enum values:

```python
class SectionType(str, Enum):
    CIS_SUMMARY = "CIS_Summary"                    # Customer Information Sheet / Key Features
    SCHEDULE_OF_BENEFITS = "Schedule_of_Benefits"  # Plan tiers, Sum Insured slabs, Sub-limits
    DEFINITIONS = "Definitions"                    # IRDAI Standard & Specific Definitions
    BASE_COVERAGE = "Base_Coverage"                # In-patient, Day care, AYUSH, Domiciliary, Restore
    OPTIONAL_RIDERS = "Optional_Riders"            # Add-ons, OPD, Maternity, Critical Illness riders
    WAITING_PERIODS = "Waiting_Periods"            # 30-day initial (Excl03), 2-yr named (Excl02), PED (Excl01)
    EXCLUSIONS = "Exclusions"                      # Standard Permanent Exclusions (Excl04-Excl18) & Specific
    COST_SHARING = "Cost_Sharing"                  # Deductibles, Co-payment, Room Rent proportionate deduction
    CLAIMS_AND_GRIEVANCE = "Claims_and_Grievance"  # Cashless/Reimbursement timelines, IRDAI Bima Bharosa / Ombudsman
```

---

## 3. Core Pydantic Data Schemas (`src/insurance_mmrag/schemas.py`)

### 3.1 `ChunkMetadata`
```python
class ChunkType(str, Enum):
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"

class ChunkMetadata(BaseModel):
    doc_id: str
    policy_name: str
    insurer_name: str
    uin: str                                       # e.g., "IRDAN000RP0001V01202021"
    section_type: SectionType
    section_title: str
    page_number: int = Field(ge=1)
    chunk_type: ChunkType
    parent_id: str
    clause_code: str | None = None                 # e.g., "Excl01", "Def.22", "Clause 3.1"
    cross_references: list[str] = Field(default_factory=list)
    image_crop_path: str | None = None
    sha256_hash: str
```

### 3.2 `ParentChunk` & `ChildChunk`
```python
class ParentChunk(BaseModel):
    parent_id: str
    doc_id: str
    section_type: SectionType
    section_title: str
    start_page: int
    end_page: int
    full_text: str
    markdown_tables: list[str] = Field(default_factory=list)
    image_crop_paths: list[str] = Field(default_factory=list)
    clause_codes: list[str] = Field(default_factory=list)

class ChildChunk(BaseModel):
    chunk_id: str
    text: str
    embedding_input: str
    metadata: ChunkMetadata
```

### 3.3 `ExtractedTableArtifact`
```python
class SyntheticQA(BaseModel):
    question: str
    answer: str

class ExtractedTableArtifact(BaseModel):
    table_id: str
    doc_id: str
    page_number: int
    section_type: SectionType
    title: str
    summary: str
    markdown_table: str
    structured_rows: list[dict[str, str | int | float | None]]
    footnotes: list[str]
    synthetic_qa_pairs: list[SyntheticQA]
    image_crop_path: str
    sha256_hash: str
```

### 3.4 `QueryIntentClassification`
```python
class QueryIntentClassification(BaseModel):
    original_query: str
    redacted_query: str
    primary_section: SectionType
    target_sections: list[SectionType]
    detected_clause_codes: list[str]
    requires_table_boost: bool
    requires_pro_escalation: bool
    rationale: str
```

### 3.5 `GroundedCitation` & `GroundedQueryResponse`
```python
class GroundedCitation(BaseModel):
    citation_id: str
    doc_id: str
    policy_name: str
    page_number: int
    section_type: SectionType
    section_title: str
    clause_code: str | None = None
    parent_id: str
    child_chunk_id: str
    chunk_type: ChunkType
    verbatim_quote: str
    parent_context_preview: str
    image_crop_url: str | None = None
    relevance_score: float = Field(ge=0.0, le=1.0)

class PolicyCoverageSummary(BaseModel):
    coverage_status: Literal["COVERED", "COVERED_WITH_LIMITS", "EXCLUDED", "WAITING_PERIOD_APPLIES", "INDETERMINATE"]
    waiting_period_details: str
    applicable_sub_limits: str
    cost_sharing_or_deductible: str
    applicable_exclusions: list[str]

class CostTelemetryRecord(BaseModel):
    operation: str
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    embedding_tokens: int
    image_count: int
    cache_hit: bool
    cost_usd: float
    cost_inr: float
    latency_ms: float

class GroundedQueryResponse(BaseModel):
    query_id: str
    answer: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    abstained: bool
    abstention_reason: str | None = None
    coverage_summary: PolicyCoverageSummary
    intent: QueryIntentClassification
    citations: list[GroundedCitation]
    cross_referenced_parents: list[str]
    pii_redactions_applied: list[str]
    cost_telemetry: CostTelemetryRecord
```

---

## 4. REST API Contract (`src/insurance_mmrag/api/main.py`)

| Method | Path | Request Body / Params | Response Model |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health` | None | `HealthResponse` (`status`, `version`, `indexed_policies`, `IndexedChunks`) |
| `GET` | `/api/v1/policies` | None | `list[PolicyDocumentSummary]` |
| `POST` | `/api/v1/ingest` | `IngestRequest` (`pdf_path` or multipart upload, `doc_id`, `insurer_name`, `uin`) | `IngestResponse` (`doc_id`, `parents_created`, `children_created`, `tables_extracted`, `cost_telemetry`) |
| `POST` | `/api/v1/query` | `QueryRequest` (`query`, `doc_id: str | None`, `top_k: int = 5`) | `GroundedQueryResponse` |
| `GET` | `/api/v1/crops/{crop_filename}` | Path param `crop_filename` | `FileResponse` (`image/png`) |
| `GET` | `/api/v1/telemetry/cost` | None | `FinOpsSummaryResponse` (Total USD/INR, cache hit ratio, per-model breakdown) |
| `GET` | `/api/v1/governance/audit` | Query param `limit: int = 50` | `list[AuditLogEntry]` |
| `POST` | `/api/v1/advisor/recommend` | `AdvisorRecommendRequest` (`user_query`, `profile`, `probing_answers`) | `AdvisorRecommendationResponse` |
| `POST` | `/api/v1/policies/compare` | `PolicyCompareRequest` (`doc_ids`, `profile`) | `PolicyComparisonResponse` |
| `POST` | `/api/v1/policies/simulate-claim` | `ClaimSimulateRequest` (`hospital_bill_inr`, `room_rent_per_day_inr`, `stay_days`, `is_cataract`) | `ClaimSimulationResponse` |
