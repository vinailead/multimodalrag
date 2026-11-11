"""Strict Pydantic v2 data contracts shared by every pipeline module, the API, and the UI."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, computed_field


class SectionType(StrEnum):
    """Canonical IRDAI functional section taxonomy."""

    CIS_SUMMARY = "CIS_Summary"
    SCHEDULE_OF_BENEFITS = "Schedule_of_Benefits"
    DEFINITIONS = "Definitions"
    BASE_COVERAGE = "Base_Coverage"
    OPTIONAL_RIDERS = "Optional_Riders"
    WAITING_PERIODS = "Waiting_Periods"
    EXCLUSIONS = "Exclusions"
    COST_SHARING = "Cost_Sharing"
    CLAIMS_AND_GRIEVANCE = "Claims_and_Grievance"


class ChunkType(StrEnum):
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"


# Binding (legally governing) sections per IRDAI: Policy Wordings & Schedule override the CIS.
BINDING_SECTIONS: tuple[SectionType, ...] = (
    SectionType.SCHEDULE_OF_BENEFITS,
    SectionType.BASE_COVERAGE,
    SectionType.WAITING_PERIODS,
    SectionType.EXCLUSIONS,
    SectionType.COST_SHARING,
)


def _empty_raw_rows() -> list[list[str]]:
    return []


def _empty_table_regions() -> list[TableRegion]:
    return []


def _empty_section_types() -> list[SectionType]:
    return []


# --------------------------------------------------------------------------- ingestion
class TextBlock(BaseModel):
    """A layout span extracted from a PDF page."""

    page_number: int = Field(ge=1)
    text: str
    font_size: float
    is_bold: bool
    bbox: tuple[float, float, float, float]


class TableRegion(BaseModel):
    page_number: int = Field(ge=1)
    bbox: tuple[float, float, float, float]
    raw_rows: list[list[str]] = Field(default_factory=_empty_raw_rows)


class DetectedSection(BaseModel):
    section_id: str
    section_type: SectionType
    title: str
    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)
    text: str
    tables: list[TableRegion] = Field(default_factory=_empty_table_regions)


class DocumentStructure(BaseModel):
    doc_id: str
    policy_name: str
    insurer_name: str
    uin: str
    page_count: int
    sections: list[DetectedSection]


class ChunkMetadata(BaseModel):
    doc_id: str
    policy_name: str
    insurer_name: str
    uin: str
    section_type: SectionType
    section_title: str
    page_number: int = Field(ge=1)
    chunk_type: ChunkType
    parent_id: str
    clause_code: str | None = None
    cross_references: list[str] = Field(default_factory=list)
    image_crop_path: str | None = None
    sha256_hash: str


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
    cross_references: list[str] = Field(default_factory=list)


class ChildChunk(BaseModel):
    chunk_id: str
    text: str
    embedding_input: str
    metadata: ChunkMetadata


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
    structured_rows: list[dict[str, str]]
    footnotes: list[str]
    synthetic_qa_pairs: list[SyntheticQA]
    image_crop_path: str
    sha256_hash: str


class IngestedDocument(BaseModel):
    structure: DocumentStructure
    parents: list[ParentChunk]
    children: list[ChildChunk]
    tables: list[ExtractedTableArtifact]

    @property
    def doc_id(self) -> str:
        return self.structure.doc_id

    @property
    def policy_name(self) -> str:
        return self.structure.policy_name

    @property
    def insurer_name(self) -> str:
        return self.structure.insurer_name

    @property
    def uin(self) -> str:
        return self.structure.uin


# --------------------------------------------------------------------------- LLM drafts
class SectionClassificationDraft(BaseModel):
    """Structured output for ambiguous-heading classification."""

    section_type: SectionType
    confidence: float = Field(ge=0.0, le=1.0)


class TableExtractionDraft(BaseModel):
    """Structured output for Gemini Vision table extraction."""

    title: str
    summary: str
    markdown_table: str
    structured_rows: list[dict[str, str]]
    footnotes: list[str]
    synthetic_qa_pairs: list[SyntheticQA]


class IntentDraft(BaseModel):
    """Structured output for pre-retrieval intent routing and CRAG sub-query decomposition."""

    primary_section: SectionType
    target_sections: list[SectionType]
    detected_clause_codes: list[str]
    sub_queries: list[str]
    requires_table_boost: bool
    requires_pro_escalation: bool
    rationale: str


# --------------------------------------------------------------------------- telemetry
class TraceSpan(BaseModel):
    """OpenTelemetry-style execution span for the agent trace waterfall."""

    span_id: str
    parent_span_id: str | None = None
    name: str
    start_offset_ms: float
    duration_ms: float
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)
    status: Literal["OK", "ERROR"] = "OK"


class CostTelemetryRecord(BaseModel):
    operation: str
    model_name: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    embedding_tokens: int = 0
    image_count: int = 0
    cache_hit: bool = False
    cost_usd: float = 0.0
    cost_inr: float = 0.0
    latency_ms: float = 0.0


class FinOpsSummary(BaseModel):
    total_cost_usd: float
    total_cost_inr: float
    total_calls: int
    cache_hits: int
    cache_hit_ratio: float
    budget_usd: float
    budget_remaining_usd: float
    per_model_usd: dict[str, float]
    total_prompt_tokens: int
    total_completion_tokens: int
    total_embedding_tokens: int

    @computed_field
    @property
    def cache_hit_rate_pct(self) -> float:
        return round(self.cache_hit_ratio * 100, 2)

    @computed_field
    @property
    def budget_utilized_pct(self) -> float:
        if self.budget_usd <= 0:
            return 0.0
        used = self.budget_usd - self.budget_remaining_usd
        return round((used / self.budget_usd) * 100, 2)

    @computed_field
    @property
    def cache_misses(self) -> int:
        return max(0, self.total_calls - self.cache_hits)

    @computed_field
    @property
    def circuit_broken(self) -> bool:
        return self.budget_remaining_usd <= 0.0


class AuditLogEntry(BaseModel):
    timestamp: str
    event_type: str
    payload: dict[str, object]
    prev_hash: str
    record_hash: str


# --------------------------------------------------------------------------- retrieval
class QueryIntentClassification(BaseModel):
    original_query: str
    redacted_query: str
    primary_section: SectionType
    target_sections: list[SectionType]
    detected_clause_codes: list[str]
    sub_queries: list[str]
    requires_table_boost: bool
    requires_pro_escalation: bool
    rationale: str


class RetrievedChunk(BaseModel):
    chunk: ChildChunk
    dense_score: float
    bm25_score: float
    rrf_score: float
    normalized_score: float = Field(ge=0.0, le=1.0)


class CragHop(BaseModel):
    """One bounded corrective-retrieval hop."""

    hop: int
    sub_query: str
    retrieved_chunk_ids: list[str]
    covered: bool
    reason: str


class PrecedenceCheck(BaseModel):
    """IRDAI rule: Policy Wordings & Schedule govern over the CIS summary."""

    cis_cited: bool
    binding_parent_ids: list[str]
    binding_sections: list[SectionType]
    rule_applied: str
    nuance_flag: bool
    note: str


class AssembledContext(BaseModel):
    parents: list[ParentChunk]
    cross_referenced_parent_ids: list[str]
    retrieved: list[RetrievedChunk]
    crag_hops: list[CragHop]
    precedence: PrecedenceCheck
    retrieval_score: float = Field(ge=0.0, le=1.0)


# --------------------------------------------------------------------------- generation
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


CoverageStatus = Literal[
    "COVERED", "COVERED_WITH_LIMITS", "EXCLUDED", "WAITING_PERIOD_APPLIES", "INDETERMINATE"
]


class PolicyCoverageSummary(BaseModel):
    coverage_status: CoverageStatus
    waiting_period_details: str
    applicable_sub_limits: str
    cost_sharing_or_deductible: str
    applicable_exclusions: list[str]


class LlmGroundedDraft(BaseModel):
    """Structured output schema requested from the generator model."""

    answer: str
    coverage_summary: PolicyCoverageSummary
    cited_chunk_ids: list[str]
    self_grounding_score: float = Field(ge=0.0, le=1.0)


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
    crag_hops: list[CragHop]
    precedence_check: PrecedenceCheck
    pii_redactions_applied: list[str]
    injection_detected: bool
    model_used: str
    trace_spans: list[TraceSpan]
    cost_telemetry: CostTelemetryRecord
    advisor_recommendation: AdvisorRecommendationResponse | None = None


# --------------------------------------------------------------------------- advisor & comparison product
def _empty_strings() -> list[str]:
    return []


class ApplicantProfile(BaseModel):
    """Structured consumer underwriting profile for policy recommendation & premium calculation."""

    proposer_age: int = Field(default=26, ge=18, le=99)
    family_size: int = Field(default=1, ge=1, le=10)
    is_smoker: bool = False
    is_drinker: bool = False
    includes_parents: bool | None = None
    eldest_member_age: int | None = None
    has_pre_existing_diseases: bool | None = None
    pre_existing_conditions: list[str] = Field(default_factory=_empty_strings)
    city_tier: Literal["tier_1", "tier_2", "tier_3"] | None = None
    target_sum_insured_inr: int = Field(default=1_000_000, ge=100_000, le=10_000_000)
    budget_priority: (
        Literal["comprehensive_zero_copay", "value_balanced", "budget_low_premium"] | None
    ) = None


class PolicyFeatureCitation(BaseModel):
    """Clause-level PDF citation backing a policy comparison cell or feature."""

    doc_id: str
    page_number: int
    section_type: SectionType
    clause_code: str | None = None
    verbatim_quote: str


class PolicyFeatureCard(BaseModel):
    """Normalized, clause-grounded product specification for an Indian insurance policy."""

    doc_id: str
    policy_name: str
    short_name: str
    insurer_name: str
    uin: str
    policy_category: Literal[
        "comprehensive_flagship",
        "value_comprehensive",
        "standard_irdai_health",
        "personal_accident",
    ]
    tagline: str
    sum_insured_options_inr: list[int]
    day_1_cover_multiplier: float = 1.0
    effective_cover_note: str
    room_rent_limit: str
    has_room_rent_cap: bool
    max_room_rent_per_day_inr: int | None = None
    room_rent_pct_of_si: float | None = None
    proportionate_deduction_applies: bool
    icu_limit: str
    ped_waiting_months: int
    specific_disease_waiting_months: int
    initial_waiting_days: int = 30
    cataract_limit_description: str
    cataract_max_per_eye_inr: int | None = None
    mandatory_copay_pct: float
    consumables_covered: bool
    consumables_note: str
    restoration_benefit: str
    no_claim_bonus_note: str
    pre_post_hospitalization: str
    ayush_coverage: str
    healthy_lifestyle_discount_pct: float
    key_strengths: list[str]
    fine_print_warnings: list[str]
    best_for_persona: str
    feature_citations: dict[str, PolicyFeatureCitation]


class PremiumBreakdown(BaseModel):
    """Transparent indicative GST-inclusive annual and monthly premium calculation."""

    doc_id: str
    policy_name: str
    sum_insured_inr: int
    effective_day_1_cover_inr: int
    pricing_age_used: int
    member_count: int
    city_tier: str
    base_annual_premium_inr: int
    floater_member_load_inr: int
    city_zone_adjustment_inr: int
    healthy_lifestyle_discount_inr: int
    smoker_loading_inr: int
    net_premium_before_gst_inr: int
    gst_18_pct_inr: int
    total_annual_premium_inr: int
    monthly_emi_inr: int
    cost_per_lakh_cover_inr: int
    pricing_notes: list[str]


class PortfolioSplitOption(BaseModel):
    """Fiduciary analysis comparing a Single Family Floater vs. Split Portfolio (Young Nuclear + Parents)."""

    recommended_strategy: Literal["SPLIT_PORTFOLIO", "SINGLE_FLOATER"]
    headline: str
    explanation: str
    single_floater_annual_inr: int
    split_young_floater_annual_inr: int
    split_parents_floater_annual_inr: int
    split_total_annual_inr: int
    annual_savings_inr: int
    combined_effective_cover_inr: int
    key_reasons_to_split: list[str]


class ProbingQuestion(BaseModel):
    """Targeted follow-up underwriting question to refine policy recommendations."""

    question_id: str
    slot_name: str
    question_text: str
    why_it_matters: str
    options: list[str]
    current_value: str | None = None


class RankedPolicyRecommendation(BaseModel):
    """Scored policy recommendation with indicative premium and personalized rationale."""

    rank: int
    badge: str
    match_score: float = Field(ge=0.0, le=100.0)
    coverage_score: float
    waiting_period_score: float
    room_rent_score: float
    value_score: float
    feature_card: PolicyFeatureCard
    premium: PremiumBreakdown
    why_recommended_for_you: list[str]
    watch_out_for: list[str]


class ComparisonCell(BaseModel):
    """Single provider cell in the side-by-side policy comparison matrix."""

    doc_id: str
    display_value: str
    sentiment: Literal["positive", "neutral", "warning", "negative"]
    is_winner: bool = False
    citation: PolicyFeatureCitation | None = None


class ComparisonRow(BaseModel):
    """Standardized IRDAI comparison parameter row across multiple policies."""

    parameter_key: str
    parameter_label: str
    consumer_tooltip: str
    cells: dict[str, ComparisonCell]


class ClaimSimulationItem(BaseModel):
    """Out-of-pocket hospital bill breakdown for a single policy."""

    doc_id: str
    policy_name: str
    short_name: str
    claimed_bill_inr: int
    room_rent_deduction_inr: int
    procedure_sublimit_deduction_inr: int
    consumables_deduction_inr: int
    copay_deduction_inr: int
    insurer_payable_inr: int
    user_out_of_pocket_inr: int
    coverage_ratio_pct: float
    explanation: str


class ClaimSimulationResponse(BaseModel):
    """Side-by-side hospital bill out-of-pocket simulation across multiple policies."""

    scenario_title: str
    procedure_type: str
    claimed_bill_inr: int
    hospital_room_rent_per_day_inr: int
    days_hospitalized: int
    sum_insured_inr: int
    results: list[ClaimSimulationItem]


class PolicyComparisonResponse(BaseModel):
    """Complete multi-policy side-by-side comparison response."""

    profile_used: ApplicantProfile
    compared_policies: list[PolicyFeatureCard]
    premiums: dict[str, PremiumBreakdown]
    comparison_rows: list[ComparisonRow]
    claim_simulation: ClaimSimulationResponse
    fiduciary_summary: str


class AdvisorRecommendationResponse(BaseModel):
    """Complete interactive needs-discovery, probing, recommendation, and comparison response."""

    query: str
    extracted_profile: ApplicantProfile
    needs_probing: bool
    completeness_pct: int
    probing_questions: list[ProbingQuestion]
    executive_advisory_summary: str
    portfolio_split_advice: PortfolioSplitOption
    ranked_policies: list[RankedPolicyRecommendation]
    comparison_matrix: list[ComparisonRow]
    claim_simulation: ClaimSimulationResponse


# --------------------------------------------------------------------------- evaluation
class GoldenExample(BaseModel):
    question: str
    expected_clause_codes: list[str] = Field(default_factory=list)
    expected_sections: list[SectionType] = Field(default_factory=_empty_section_types)
    expected_numbers: list[str] = Field(default_factory=list)
    should_abstain: bool = False


class BenchmarkCaseResult(BaseModel):
    question: str
    context_recall: float
    faithfulness: float
    abstained: bool
    should_abstain: bool
    table_exact: float | None
    confidence: float


class RAGTriadScorecard(BaseModel):
    context_recall_at_k: float
    answer_faithfulness: float
    abstention_f1: float
    table_numerical_exactness: float
    total_cases: int
    total_cost_usd: float
    cases: list[BenchmarkCaseResult]


GroundedQueryResponse.model_rebuild()
