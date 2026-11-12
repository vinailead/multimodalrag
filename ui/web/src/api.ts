/**
 * Strongly typed FastAPI REST API Client for Indian Insurance Multimodal RAG.
 */

import type {
  AdvisorRecommendationResponse,
  ApplicantProfile,
  ClaimSimulationResponse,
  FinOpsSummary,
  GroundedQueryResponse,
  HealthStatus,
  IndexedPolicy,
  McpToolDefinition,
  PolicyComparisonResponse,
  RAGTriadScorecard,
} from "./types.ts";

const BASE_URL = "";

export async function fetchHealth(): Promise<HealthStatus> {
  const resp = await fetch(`${BASE_URL}/api/v1/health`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch health: ${resp.statusText}`);
  }
  return (await resp.json()) as HealthStatus;
}

export async function fetchPolicies(): Promise<IndexedPolicy[]> {
  const resp = await fetch(`${BASE_URL}/api/v1/policies`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch policies: ${resp.statusText}`);
  }
  return (await resp.json()) as IndexedPolicy[];
}

export async function submitQuery(
  query: string,
  docId?: string,
  topK: number = 4,
): Promise<GroundedQueryResponse> {
  const payload: { query: string; doc_id?: string; top_k: number } = {
    query,
    top_k: topK,
  };
  if (docId) {
    payload.doc_id = docId;
  }
  const resp = await fetch(`${BASE_URL}/api/v1/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    throw new Error(`Query failed with status ${resp.status}: ${resp.statusText}`);
  }
  return (await resp.json()) as GroundedQueryResponse;
}

export async function fetchFinOps(): Promise<FinOpsSummary> {
  const resp = await fetch(`${BASE_URL}/api/v1/telemetry/cost`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch FinOps telemetry: ${resp.statusText}`);
  }
  return (await resp.json()) as FinOpsSummary;
}

export async function fetchBenchmarkScorecard(): Promise<RAGTriadScorecard> {
  const resp = await fetch(`${BASE_URL}/api/v1/benchmark/scorecard`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch benchmark scorecard: ${resp.statusText}`);
  }
  return (await resp.json()) as RAGTriadScorecard;
}

export async function fetchMcpTools(): Promise<McpToolDefinition[]> {
  const resp = await fetch(`${BASE_URL}/api/v1/mcp/tools`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch MCP tools: ${resp.statusText}`);
  }
  return (await resp.json()) as McpToolDefinition[];
}

export async function executeMcpTool(
  toolName: string,
  args: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const resp = await fetch(`${BASE_URL}/api/v1/mcp/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool_name: toolName, arguments: args }),
  });
  if (!resp.ok) {
    throw new Error(`Failed to execute MCP tool: ${resp.statusText}`);
  }
  return (await resp.json()) as Record<string, unknown>;
}

export async function fetchAdvisorRecommendation(
  userQuery: string,
  profile?: Partial<ApplicantProfile>,
  probingAnswers?: Record<string, string>,
): Promise<AdvisorRecommendationResponse> {
  const extraParts = probingAnswers ? Object.values(probingAnswers).join(". ") : "";
  const effectiveQuery = extraParts ? `${userQuery}. ${extraParts}` : userQuery;
  const payload: Record<string, unknown> = {
    query: effectiveQuery,
  };
  if (profile) {
    payload.profile = profile;
  }
  const resp = await fetch(`${BASE_URL}/api/v1/advisor/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    throw new Error(`Failed to fetch advisor recommendation: ${resp.statusText}`);
  }
  return (await resp.json()) as AdvisorRecommendationResponse;
}

export async function fetchPolicyComparison(
  docIds?: string[],
  profile?: Partial<ApplicantProfile>,
): Promise<PolicyComparisonResponse> {
  const payload: Record<string, unknown> = {};
  if (docIds && docIds.length > 0) {
    payload.doc_ids = docIds;
  }
  if (profile) {
    payload.profile = profile;
  }
  const resp = await fetch(`${BASE_URL}/api/v1/policies/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    throw new Error(`Failed to fetch policy comparison: ${resp.statusText}`);
  }
  return (await resp.json()) as PolicyComparisonResponse;
}

export async function fetchClaimSimulation(params: {
  doc_ids?: string[];
  claimed_bill_inr: number;
  hospital_room_rent_per_day_inr: number;
  days_hospitalized: number;
  procedure_type?: string;
  sum_insured_inr?: number;
}): Promise<ClaimSimulationResponse> {
  const resp = await fetch(`${BASE_URL}/api/v1/policies/simulate-claim`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!resp.ok) {
    throw new Error(`Failed to simulate claim: ${resp.statusText}`);
  }
  return (await resp.json()) as ClaimSimulationResponse;
}
