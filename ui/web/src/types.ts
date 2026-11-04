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
