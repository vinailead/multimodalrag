/**
 * TypeScript domain types mirroring backend Pydantic schemas (`src/insurance_mmrag/schemas.py`).
 */

export interface CostTelemetry {
  prompt_tokens: number;
  completion_tokens: number;
  embedding_tokens: number;
  image_count: number;
  cache_hit: boolean;
  cost_usd: number;
  cost_inr: number;
  latency_ms: number;
}

export interface TraceSpan {
  span_id: string;
  parent_span_id: string | null;
  name: string;
  start_offset_ms: number;
  duration_ms: number;
  attributes: Record<string, string | number | boolean>;
  status: "OK" | "ERROR";
}

export interface GroundedCitation {
  citation_id: string;
  doc_id: string;
  policy_name: string;
  page_number: number;
  section_type: string;
  section_title: string;
  clause_code: string | null;
  parent_id: string;
  child_chunk_id: string;
  chunk_type: string;
  verbatim_quote: string;
  parent_context_preview: string;
  image_crop_url: string | null;
  relevance_score: number;
}

export interface PolicyCoverageSummary {
  coverage_status:
    "COVERED" | "COVERED_WITH_LIMITS" | "WAITING_PERIOD_APPLIES" | "EXCLUDED" | "INDETERMINATE";
  waiting_period_details: string;
  applicable_sub_limits: string;
  cost_sharing_or_deductible: string;
  applicable_exclusions: string[];
}

export interface QueryIntentClassification {
  original_query: string;
  redacted_query: string;
  primary_section: string;
  confidence?: number;
  sub_queries: string[];
  clause_codes?: string[];
  detected_clause_codes?: string[];
  requires_table_search?: boolean;
  requires_table_boost?: boolean;
  requires_pro_escalation: boolean;
  pii_detected?: string[];
}

export interface PrecedenceCheckResult {
  cis_cited: boolean;
  binding_parent_ids: string[];
  binding_sections: string[];
  rule_applied: string;
  nuance_flag: boolean;
  note: string;
}

export interface ApplicantProfile {
  proposer_age: number;
  family_size: number;
  is_smoker: boolean;
  is_drinker: boolean;
  includes_parents: boolean | null;
  eldest_member_age: number | null;
  has_pre_existing_diseases: boolean | null;
  pre_existing_conditions: string[];
  city_tier: "tier_1" | "tier_2" | "tier_3" | null;
  target_sum_insured_inr: number;
  budget_priority: "comprehensive_zero_copay" | "value_balanced" | "budget_low_premium" | null;
}

export interface PolicyFeatureCitation {
  doc_id: string;
  page_number: number;
  section_type: string;
  clause_code: string | null;
  verbatim_quote: string;
}

export interface PolicyFeatureCard {
  doc_id: string;
  policy_name: string;
  short_name: string;
  insurer_name: string;
  uin: string;
  policy_category:
    | "comprehensive_flagship"
    | "value_comprehensive"
    | "standard_irdai_health"
    | "personal_accident";
  tagline: string;
  sum_insured_options_inr: number[];
  day_1_cover_multiplier: number;
  effective_cover_note: string;
  room_rent_limit: string;
  has_room_rent_cap: boolean;
  max_room_rent_per_day_inr: number | null;
  room_rent_pct_of_si: number | null;
  proportionate_deduction_applies: boolean;
  icu_limit: string;
  ped_waiting_months: number;
  specific_disease_waiting_months: number;
  initial_waiting_days: number;
  cataract_limit_description: string;
  cataract_max_per_eye_inr: number | null;
  mandatory_copay_pct: number;
  consumables_covered: boolean;
  consumables_note: string;
  restoration_benefit: string;
  no_claim_bonus_note: string;
  pre_post_hospitalization: string;
  ayush_coverage: string;
  healthy_lifestyle_discount_pct: number;
  key_strengths: string[];
  fine_print_warnings: string[];
  best_for_persona: string;
  feature_citations: Record<string, PolicyFeatureCitation>;
}

export interface PremiumBreakdown {
  doc_id: string;
  policy_name: string;
  sum_insured_inr: number;
  effective_day_1_cover_inr: number;
  pricing_age_used: number;
  member_count: number;
  city_tier: string;
  base_annual_premium_inr: number;
  floater_member_load_inr: number;
  city_zone_adjustment_inr: number;
  healthy_lifestyle_discount_inr: number;
  smoker_loading_inr: number;
  net_premium_before_gst_inr: number;
  gst_18_pct_inr: number;
  total_annual_premium_inr: number;
  monthly_emi_inr: number;
  cost_per_lakh_cover_inr: number;
  pricing_notes: string[];
}

export interface PortfolioSplitOption {
  recommended_strategy: "SPLIT_PORTFOLIO" | "SINGLE_FLOATER";
  headline: string;
  explanation: string;
  single_floater_annual_inr: number;
  split_young_floater_annual_inr: number;
  split_parents_floater_annual_inr: number;
  split_total_annual_inr: number;
  annual_savings_inr: number;
  combined_effective_cover_inr: number;
  key_reasons_to_split: string[];
}

export interface ProbingQuestion {
  question_id: string;
  slot_name: string;
  question_text: string;
  why_it_matters: string;
  options: string[];
  current_value?: string | null;
}

export interface RankedPolicyRecommendation {
  rank: number;
  badge: string;
  match_score: number;
  coverage_score: number;
  waiting_period_score: number;
  room_rent_score: number;
  value_score: number;
  feature_card: PolicyFeatureCard;
  premium: PremiumBreakdown;
  why_recommended_for_you: string[];
  watch_out_for: string[];
}

export interface ComparisonCell {
  doc_id: string;
  display_value: string;
  sentiment: "positive" | "neutral" | "warning" | "negative";
  is_winner: boolean;
  citation: PolicyFeatureCitation | null;
}

export interface ComparisonRow {
  parameter_key: string;
  parameter_label: string;
  consumer_tooltip: string;
  cells: Record<string, ComparisonCell>;
}

export interface ClaimSimulationItem {
  doc_id: string;
  policy_name: string;
  short_name: string;
  claimed_bill_inr: number;
  room_rent_deduction_inr: number;
  procedure_sublimit_deduction_inr: number;
  consumables_deduction_inr: number;
  copay_deduction_inr: number;
  insurer_payable_inr: number;
  user_out_of_pocket_inr: number;
  coverage_ratio_pct: number;
  explanation: string;
}

export interface ClaimSimulationResponse {
  scenario_title: string;
  procedure_type: string;
  claimed_bill_inr: number;
  hospital_room_rent_per_day_inr: number;
  days_hospitalized: number;
  sum_insured_inr: number;
  results: ClaimSimulationItem[];
}

export interface PolicyComparisonResponse {
  profile_used: ApplicantProfile;
  compared_policies: PolicyFeatureCard[];
  premiums: Record<string, PremiumBreakdown>;
  comparison_rows: ComparisonRow[];
  claim_simulation: ClaimSimulationResponse;
  fiduciary_summary: string;
}

export interface AdvisorRecommendationResponse {
  query: string;
  extracted_profile: ApplicantProfile;
  needs_probing: boolean;
  completeness_pct: number;
  probing_questions: ProbingQuestion[];
  executive_advisory_summary: string;
  portfolio_split_advice: PortfolioSplitOption;
  ranked_policies: RankedPolicyRecommendation[];
  comparison_matrix: ComparisonRow[];
  claim_simulation: ClaimSimulationResponse;
}

export interface GroundedQueryResponse {
  query_id: string;
  answer: string;
  confidence_score: number;
  abstained: boolean;
  abstention_reason: string | null;
  coverage_summary: PolicyCoverageSummary;
  intent: QueryIntentClassification;
  citations: GroundedCitation[];
  cross_referenced_parents: string[];
  crag_hops: number | unknown[];
  precedence_check: PrecedenceCheckResult;
  pii_redactions_applied: string[];
  injection_detected: boolean;
  model_used: string;
  trace_spans: TraceSpan[];
  cost_telemetry: CostTelemetry;
  advisor_recommendation?: AdvisorRecommendationResponse | null;
}

export interface IndexedPolicy {
  doc_id: string;
  policy_name: string;
  insurer_name: string;
  uin: string;
  page_count: number;
  sections_count?: number;
  parents_count?: number;
  children_count?: number;
  tables_count: number;
  chunks_count?: number;
}

export interface FinOpsSummary {
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_embedding_tokens: number;
  total_images_processed: number;
  total_cost_usd: number;
  total_cost_inr: number;
  budget_usd: number;
  budget_utilized_pct: number;
  cache_hits: number;
  cache_misses: number;
  cache_hit_rate_pct: number;
  circuit_broken: boolean;
}

export interface BenchmarkCaseResult {
  question: string;
  context_recall: number;
  faithfulness: number;
  abstained: boolean;
  should_abstain: boolean;
  table_exact: number | null;
  confidence: number;
}

export interface RAGTriadScorecard {
  context_recall_at_k: number;
  answer_faithfulness: number;
  abstention_f1: number;
  table_numerical_exactness: number;
  total_cases: number;
  total_cost_usd: number;
  cases: BenchmarkCaseResult[];
}

export interface McpToolDefinition {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

export interface HealthStatus {
  status: string;
  version: string;
  vector_store: string;
  indexed_policies_count: number;
}
