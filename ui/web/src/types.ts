/**
 * TypeScript domain types mirroring backend Pydantic schemas.
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
  confidence: number;
  sub_queries: string[];
  clause_codes: string[];
  requires_table_search: boolean;
  requires_pro_escalation: boolean;
  pii_detected: string[];
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
  primary_age: number;
  eldest_member_age: number;
  family_size: number;
  includes_parents: boolean | null;
  parents_eldest_age: number | null;
  smoker: boolean;
  drinker: boolean;
  has_pre_existing_diseases: boolean | null;
  pre_existing_conditions: string[];
  maternity_needed: boolean | null;
  city_tier: "TIER_1_METRO" | "TIER_2" | "TIER_3" | null;
  target_sum_insured_inr: number;
  budget_priority: "LOWEST_PREMIUM" | "BALANCED" | "MAXIMUM_COVERAGE" | null;
}

export interface PolicyFeatureCitation {
  doc_id: string;
  policy_name: string;
  section_title: string;
  clause_code: string | null;
  page_number: number;
  verbatim_quote: string;
}

export interface PolicyFeatureCard {
  doc_id: string;
  policy_name: string;
  insurer_name: string;
  uin: string;
  product_type: "HEALTH_INDIVIDUAL_FLOATER" | "PERSONAL_ACCIDENT";
  positioning_tier: "ULTRA_COMPREHENSIVE" | "PREMIUM_METRO" | "BALANCED_FAMILY" | "VALUE_STANDARD";
  eligible_sum_insured_options_inr: number[];
  default_sum_insured_inr: number;
  room_rent_limit: string;
  room_rent_capped: boolean;
  room_rent_max_pct_per_day: number | null;
  room_rent_max_inr_per_day: number | null;
  cataract_limit: string;
  cataract_max_per_eye_inr: number | null;
  ped_waiting_months: number;
  specific_disease_waiting_months: number;
  initial_waiting_days: number;
  mandatory_copay_pct: number;
  restoration_benefit: string;
  no_claim_bonus: string;
  consumables_covered: boolean;
  maternity_covered: boolean;
  ayush_coverage: string;
  day_care_procedures: string;
  modern_treatments_coverage: string;
  key_highlights: string[];
  watch_outs: string[];
  feature_citations: Record<string, PolicyFeatureCitation>;
}

export interface PremiumBreakdown {
  doc_id: string;
  policy_name: string;
  sum_insured_inr: number;
  eldest_age_used: number;
  family_size_used: number;
  base_annual_premium_inr: number;
  family_floater_load_inr: number;
  healthy_lifestyle_discount_inr: number;
  subtotal_before_gst_inr: number;
  gst_18_pct_inr: number;
  total_annual_premium_inr: number;
  monthly_emi_inr: number;
  pricing_notes: string[];
}

export interface PortfolioSplitOption {
  recommended: boolean;
  headline: string;
  rationale: string;
  single_floater_doc_id: string;
  single_floater_annual_inr: number;
  young_family_doc_id: string;
  young_family_policy_name: string;
  young_family_annual_inr: number;
  parents_doc_id: string;
  parents_policy_name: string;
  parents_annual_inr: number;
  combined_split_annual_inr: number;
  annual_savings_inr: number;
}

export interface ProbingQuestion {
  question_id: string;
  slot_name: string;
  question_text: string;
  why_it_matters: string;
  options: string[];
}

export interface RankedPolicyRecommendation {
  rank: number;
  match_score_pct: number;
  badge_label: string;
  policy: PolicyFeatureCard;
  premium: PremiumBreakdown;
  why_this_fits: string[];
  trade_offs: string[];
}

export interface ComparisonCell {
  doc_id: string;
  policy_name: string;
  display_value: string;
  is_best_in_class: boolean;
  sentiment: "POSITIVE" | "NEUTRAL" | "WARNING";
  citation: PolicyFeatureCitation | null;
}

export interface ComparisonRow {
  parameter_key: string;
  parameter_label: string;
  category: string;
  cells: ComparisonCell[];
}

export interface ClaimSimulationItem {
  doc_id: string;
  policy_name: string;
  hospital_bill_inr: number;
  room_rent_deduction_inr: number;
  sub_limit_deduction_inr: number;
  consumables_deduction_inr: number;
  copay_deduction_inr: number;
  insurer_payable_inr: number;
  out_of_pocket_inr: number;
  explanation: string;
}

export interface ClaimSimulationResponse {
  scenario_title: string;
  hospital_bill_inr: number;
  room_rent_per_day_inr: number;
  stay_days: number;
  is_cataract: boolean;
  results: ClaimSimulationItem[];
}

export interface PolicyComparisonResponse {
  compared_policies: PolicyFeatureCard[];
  premiums: Record<string, PremiumBreakdown>;
  comparison_rows: ComparisonRow[];
  claim_simulation: ClaimSimulationResponse;
  executive_verdict: string;
}

export interface AdvisorRecommendationResponse {
  extracted_profile: ApplicantProfile;
  profile_completeness_pct: number;
  needs_more_info: boolean;
  probing_questions: ProbingQuestion[];
  portfolio_split_analysis: PortfolioSplitOption | null;
  recommendations: RankedPolicyRecommendation[];
  comparison_matrix: PolicyComparisonResponse;
  advisory_summary: string;
  irdai_disclaimer: string;
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
  crag_hops: number;
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
  sections_count: number;
  tables_count: number;
  chunks_count: number;
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
