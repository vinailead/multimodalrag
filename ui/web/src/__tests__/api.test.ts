import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  executeMcpTool,
  fetchBenchmarkScorecard,
  fetchFinOps,
  fetchHealth,
  fetchMcpTools,
  fetchPolicies,
  submitQuery,
} from "../api.ts";

describe("API Client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchHealth returns health status or throws on error", async () => {
    const mockHealth = {
      status: "healthy",
      version: "1.0.0",
      vector_store: "ready",
      indexed_policies_count: 2,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockHealth,
    } as Response);

    const res = await fetchHealth();
    expect(res.status).toBe("healthy");
    expect(res.version).toBe("1.0.0");

    // Error case
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      statusText: "Internal Error",
    } as Response);
    await expect(fetchHealth()).rejects.toThrow("Failed to fetch health");
  });

  it("fetchPolicies returns indexed policies or throws on error", async () => {
    const mockPolicies = [
      {
        doc_id: "arogya",
        policy_name: "Arogya Sanjeevani",
        insurer_name: "IRDAI",
        uin: "IRDAI/NL-HLT/2020",
        page_count: 6,
        sections_count: 8,
        tables_count: 1,
        chunks_count: 45,
      },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockPolicies,
    } as Response);

    const res = await fetchPolicies();
    expect(res.length).toBe(1);
    expect(res[0].policy_name).toBe("Arogya Sanjeevani");

    // Error case
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      statusText: "Bad Gateway",
    } as Response);
    await expect(fetchPolicies()).rejects.toThrow("Failed to fetch policies");
  });

  it("submitQuery sends POST with payload and returns GroundedQueryResponse", async () => {
    const mockResponse = {
      query_id: "qry_123",
      answer: "Sample answer",
      confidence_score: 0.88,
      abstained: false,
      abstention_reason: null,
      coverage_summary: {
        coverage_status: "COVERED",
        waiting_period_details: "None",
        applicable_sub_limits: "None",
        cost_sharing_or_deductible: "None",
        applicable_exclusions: [],
      },
      intent: {
        original_query: "Query",
        redacted_query: "Query",
        primary_section: "BASE_COVERAGE",
        confidence: 0.9,
        sub_queries: [],
        clause_codes: [],
        requires_table_search: false,
        requires_pro_escalation: false,
        pii_detected: [],
      },
      citations: [],
      cross_referenced_parents: [],
      crag_hops: 0,
      precedence_check: {
        cis_cited: false,
        binding_parent_ids: [],
        binding_sections: [],
        rule_applied: "Standard Policy Wordings Direct Citation.",
        nuance_flag: false,
        note: "Direct interpretation.",
      },
      pii_redactions_applied: [],
      injection_detected: false,
      model_used: "gemini-2.5-flash",
      trace_spans: [],
      cost_telemetry: {
        prompt_tokens: 10,
        completion_tokens: 10,
        embedding_tokens: 0,
        image_count: 0,
        cache_hit: false,
        cost_usd: 0.0001,
        cost_inr: 0.008,
        latency_ms: 50,
      },
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    const res = await submitQuery("Query", "arogya", 5);
    expect(res.query_id).toBe("qry_123");
    expect(res.answer).toBe("Sample answer");

    // Error case
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Error",
    } as Response);
    await expect(submitQuery("Fail")).rejects.toThrow("Query failed with status 500");
  });

  it("fetchFinOps returns telemetry summary or throws on error", async () => {
    const mockFinOps = {
      total_prompt_tokens: 100,
      total_completion_tokens: 50,
      total_embedding_tokens: 20,
      total_images_processed: 1,
      total_cost_usd: 0.001,
      total_cost_inr: 0.08,
      budget_usd: 10.0,
      budget_utilized_pct: 0.01,
      cache_hits: 1,
      cache_misses: 1,
      cache_hit_rate_pct: 50.0,
      circuit_broken: false,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockFinOps,
    } as Response);

    const res = await fetchFinOps();
    expect(res.total_cost_usd).toBe(0.001);

    // Error case
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      statusText: "Not Found",
    } as Response);
    await expect(fetchFinOps()).rejects.toThrow("Failed to fetch FinOps telemetry");
  });

  it("fetchBenchmarkScorecard returns triad metrics or throws on error", async () => {
    const mockCard = {
      context_recall_at_k: 0.85,
      answer_faithfulness: 0.88,
      abstention_f1: 1.0,
      table_numerical_exactness: 0.9,
      total_cases: 5,
      total_cost_usd: 0.002,
      cases: [],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockCard,
    } as Response);

    const res = await fetchBenchmarkScorecard();
    expect(res.context_recall_at_k).toBe(0.85);

    // Error case
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      statusText: "Error",
    } as Response);
    await expect(fetchBenchmarkScorecard()).rejects.toThrow("Failed to fetch benchmark scorecard");
  });

  it("fetchMcpTools returns tool list or throws on error", async () => {
    const mockTools = [{ name: "tool1", description: "desc", parameters: {} }];
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockTools,
    } as Response);

    const res = await fetchMcpTools();
    expect(res.length).toBe(1);

    // Error case
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      statusText: "Error",
    } as Response);
    await expect(fetchMcpTools()).rejects.toThrow("Failed to fetch MCP tools");
  });

  it("executeMcpTool posts payload and returns result or throws on error", async () => {
    const mockResult = { result: "ok" };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockResult,
    } as Response);

    const res = await executeMcpTool("lookup", { code: "Excl01" });
    expect(res.result).toBe("ok");

    // Error case
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      statusText: "Internal Error",
    } as Response);
    await expect(executeMcpTool("fail", {})).rejects.toThrow("Failed to execute MCP tool");
  });
});
