import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  executeMcpTool,
  fetchAdvisorRecommendation,
  fetchBenchmarkScorecard,
  fetchClaimSimulation,
  fetchFinOps,
  fetchHealth,
  fetchMcpTools,
  fetchPolicies,
  fetchPolicyComparison,
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

  it("fetchAdvisorRecommendation posts query and returns AdvisorRecommendationResponse", async () => {
    const mockAdvisor = {
      query: "26yo non smoker family of 5",
      extracted_profile: {
        proposer_age: 26,
        eldest_member_age: null,
        family_size: 5,
        includes_parents: null,
        is_smoker: false,
        is_drinker: false,
        has_pre_existing_diseases: null,
        pre_existing_conditions: [],
        city_tier: null,
        target_sum_insured_inr: 1000000,
        budget_priority: null,
      },
      completeness_pct: 50,
      needs_probing: true,
      probing_questions: [],
      executive_advisory_summary: "Summary",
      portfolio_split_advice: {
        recommended_strategy: "SPLIT_PORTFOLIO",
        headline: "Headline",
        explanation: "Explanation",
        single_floater_annual_inr: 45000,
        split_young_floater_annual_inr: 15000,
        split_parents_floater_annual_inr: 22000,
        split_total_annual_inr: 37000,
        annual_savings_inr: 8000,
        combined_effective_cover_inr: 2000000,
        key_reasons_to_split: [],
      },
      ranked_policies: [],
      comparison_matrix: [],
      claim_simulation: {
        scenario_title: "Test",
        procedure_type: "general",
        claimed_bill_inr: 250000,
        hospital_room_rent_per_day_inr: 9000,
        days_hospitalized: 4,
        sum_insured_inr: 1000000,
        results: [],
      },
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockAdvisor,
    } as Response);

    const res = await fetchAdvisorRecommendation(
      "26yo non smoker family of 5",
      { proposer_age: 26 },
      { includes_parents: "No — Spouse & Kids only (all under 35)" },
    );
    expect(res.extracted_profile.proposer_age).toBe(26);
    expect(res.extracted_profile.family_size).toBe(5);

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      statusText: "Bad Request",
    } as Response);
    await expect(fetchAdvisorRecommendation("fail")).rejects.toThrow(
      "Failed to fetch advisor recommendation",
    );
  });

  it("fetchPolicyComparison posts doc_ids and profile and returns PolicyComparisonResponse", async () => {
    const mockComp = {
      profile_used: {
        proposer_age: 26,
        family_size: 5,
        is_smoker: false,
        is_drinker: false,
        includes_parents: null,
        eldest_member_age: null,
        has_pre_existing_diseases: null,
        pre_existing_conditions: [],
        city_tier: null,
        target_sum_insured_inr: 1000000,
        budget_priority: null,
      },
      compared_policies: [],
      premiums: {},
      comparison_rows: [],
      claim_simulation: {
        scenario_title: "Test",
        procedure_type: "general",
        claimed_bill_inr: 250000,
        hospital_room_rent_per_day_inr: 9000,
        days_hospitalized: 4,
        sum_insured_inr: 1000000,
        results: [],
      },
      fiduciary_summary: "Comparison Verdict",
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockComp,
    } as Response);

    const res = await fetchPolicyComparison(["hdfc_ergo_optima_secure"], { proposer_age: 26 });
    expect(res.fiduciary_summary).toBe("Comparison Verdict");

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      statusText: "Server Error",
    } as Response);
    await expect(fetchPolicyComparison()).rejects.toThrow("Failed to fetch policy comparison");
  });

  it("fetchClaimSimulation posts hospital scenario and returns ClaimSimulationResponse", async () => {
    const mockSim = {
      scenario_title: "Cardiac",
      procedure_type: "cardiac",
      claimed_bill_inr: 250000,
      hospital_room_rent_per_day_inr: 9000,
      days_hospitalized: 4,
      sum_insured_inr: 1000000,
      results: [],
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockSim,
    } as Response);

    const res = await fetchClaimSimulation({
      claimed_bill_inr: 250000,
      hospital_room_rent_per_day_inr: 9000,
      days_hospitalized: 4,
    });
    expect(res.claimed_bill_inr).toBe(250000);

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      statusText: "Error",
    } as Response);
    await expect(
      fetchClaimSimulation({
        claimed_bill_inr: 100000,
        hospital_room_rent_per_day_inr: 5000,
        days_hospitalized: 2,
      }),
    ).rejects.toThrow("Failed to simulate claim");
  });
});
