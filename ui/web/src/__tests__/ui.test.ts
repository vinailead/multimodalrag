import { describe, expect, it, vi } from "vitest";
import {
  renderCitationChips,
  renderConfidenceBadge,
  renderFinOpsPanel,
  renderInspector,
  renderIntentChips,
  renderMcpToolsPanel,
  renderPolicyBreakdown,
  renderScorecardPanel,
  renderTraceWaterfall,
} from "../components.ts";
import type {
  FinOpsSummary,
  GroundedCitation,
  McpToolDefinition,
  PolicyCoverageSummary,
  QueryIntentClassification,
  RAGTriadScorecard,
  TraceSpan,
} from "../types.ts";

describe("Material Design 3 Components", () => {
  describe("renderConfidenceBadge", () => {
    it("renders verified green badge when score >= 0.70 and not abstained", () => {
      const el = renderConfidenceBadge(0.852, false);
      expect(el.classList.contains("m3-badge-verified")).toBe(true);
      expect(el.textContent).toContain("85.2%");
      expect(el.textContent).toContain("(Verified)");
    });

    it("renders error red badge when score < 0.70", () => {
      const el = renderConfidenceBadge(0.64, false);
      expect(el.classList.contains("m3-badge-error")).toBe(true);
      expect(el.textContent).toContain("64.0%");
      expect(el.textContent).toContain("(Abstained)");
    });

    it("renders error red badge when abstained is true regardless of score", () => {
      const el = renderConfidenceBadge(0.92, true);
      expect(el.classList.contains("m3-badge-error")).toBe(true);
      expect(el.textContent).toContain("(Abstained)");
    });
  });

  describe("renderIntentChips", () => {
    it("renders primary section chip, sub-queries, and model tier", () => {
      const intent: QueryIntentClassification = {
        original_query: "What is the waiting period for cataract surgery?",
        redacted_query: "What is the waiting period for cataract surgery?",
        primary_section: "WAITING_PERIODS",
        confidence: 0.95,
        sub_queries: ["cataract surgery limit", "specified disease waiting period"],
        clause_codes: ["Excl02"],
        requires_table_search: true,
        requires_pro_escalation: false,
        pii_detected: [],
      };
      const el = renderIntentChips(intent);
      expect(el.textContent).toContain("Intent: WAITING_PERIODS");
      expect(el.textContent).toContain("CRAG Sub-query: cataract surgery limit");
      expect(el.textContent).toContain("Model: Gemini 2.5 Flash");
    });

    it("renders Pro escalation badge when requires_pro_escalation is true", () => {
      const intent: QueryIntentClassification = {
        original_query: "Compare schedule and wordings for cataract",
        redacted_query: "Compare schedule and wordings for cataract",
        primary_section: "SCHEDULE_OF_BENEFITS",
        confidence: 0.88,
        sub_queries: [],
        clause_codes: [],
        requires_table_search: true,
        requires_pro_escalation: true,
        pii_detected: [],
      };
      const el = renderIntentChips(intent);
      expect(el.textContent).toContain("Gemini 2.5 Pro (Escalated)");
    });
  });

  describe("renderPolicyBreakdown", () => {
    it("renders structured breakdown table with coverage status and exclusions", () => {
      const summary: PolicyCoverageSummary = {
        coverage_status: "COVERED_WITH_LIMITS",
        waiting_period_details: "24 months for specified surgeries",
        applicable_sub_limits: "Up to ₹40,000 per eye",
        cost_sharing_or_deductible: "5% mandatory co-payment",
        applicable_exclusions: ["Excl02", "Excl03"],
      };
      const el = renderPolicyBreakdown(summary);
      expect(el.tagName).toBe("TABLE");
      expect(el.textContent).toContain("COVERED_WITH_LIMITS");
      expect(el.textContent).toContain("24 months for specified surgeries");
      expect(el.textContent).toContain("Up to ₹40,000 per eye");
      expect(el.textContent).toContain("Excl02");
    });
  });

  describe("renderCitationChips", () => {
    it("renders clickable citation chips with data-testid and handles clicks", () => {
      const citations: GroundedCitation[] = [
        {
          citation_id: "cit_01",
          doc_id: "arogya",
          policy_name: "Arogya Sanjeevani",
          page_number: 2,
          section_type: "SCHEDULE_OF_BENEFITS",
          section_title: "Table of Benefits",
          clause_code: null,
          parent_id: "par_01",
          child_chunk_id: "chk_01",
          chunk_type: "TABLE",
          verbatim_quote: "Cataract per eye up to ₹40,000.",
          parent_context_preview: "Full Schedule context",
          image_crop_url: "/api/v1/crops/crop1.png",
          relevance_score: 0.88,
        },
      ];
      const onSelect = vi.fn();
      const el = renderCitationChips(citations, onSelect);
      const button = el.querySelector("button");
      expect(button).not.toBeNull();
      expect(button?.getAttribute("data-testid")).toBe("citation-chip-0");

      button?.click();
      expect(onSelect).toHaveBeenCalledTimes(1);
      expect(onSelect).toHaveBeenCalledWith(citations[0]);
    });

    it("renders empty state notice when no citations are provided", () => {
      const el = renderCitationChips([], () => {});
      expect(el.textContent).toContain("No citations available");
    });
  });

  describe("renderTraceWaterfall", () => {
    it("renders waterfall timeline spans with durations", () => {
      const spans: TraceSpan[] = [
        {
          span_id: "span_1",
          parent_span_id: null,
          name: "retrieval.intent_route",
          start_offset_ms: 0.1,
          duration_ms: 12.5,
          attributes: {},
          status: "OK",
        },
        {
          span_id: "span_2",
          parent_span_id: "span_1",
          name: "generation.grounded_synthesis",
          start_offset_ms: 13.0,
          duration_ms: 45.2,
          attributes: {},
          status: "OK",
        },
      ];
      const el = renderTraceWaterfall(spans);
      expect(el.textContent).toContain("retrieval.intent_route");
      expect(el.textContent).toContain("12.5ms");
      expect(el.textContent).toContain("45.2ms");
    });

    it("handles empty spans gracefully", () => {
      const el = renderTraceWaterfall([]);
      expect(el.textContent).toContain("No spans recorded");
    });
  });

  describe("renderFinOpsPanel", () => {
    it("formats and displays USD and INR spend metrics", () => {
      const finops: FinOpsSummary = {
        total_prompt_tokens: 1200,
        total_completion_tokens: 300,
        total_embedding_tokens: 450,
        total_images_processed: 2,
        total_cost_usd: 0.00152,
        total_cost_inr: 0.127,
        budget_usd: 10.0,
        budget_utilized_pct: 0.015,
        cache_hits: 4,
        cache_misses: 1,
        cache_hit_rate_pct: 80.0,
        circuit_broken: false,
      };
      const el = renderFinOpsPanel(finops);
      expect(el.textContent).toContain("$0.0015");
      expect(el.textContent).toContain("₹0.13");
      expect(el.textContent).toContain("80.0%");
    });
  });

  describe("renderScorecardPanel", () => {
    it("displays RAG triad metrics accurately", () => {
      const scorecard: RAGTriadScorecard = {
        context_recall_at_k: 0.885,
        answer_faithfulness: 0.912,
        abstention_f1: 1.0,
        table_numerical_exactness: 0.85,
        total_cases: 7,
        total_cost_usd: 0.0035,
        cases: [],
      };
      const el = renderScorecardPanel(scorecard);
      expect(el.textContent).toContain("88.5%");
      expect(el.textContent).toContain("91.2%");
      expect(el.textContent).toContain("100.0%");
      expect(el.textContent).toContain("85.0%");
    });
  });

  describe("renderMcpToolsPanel", () => {
    it("renders MCP tools list", () => {
      const tools: McpToolDefinition[] = [
        {
          name: "query_irdai_policy",
          description: "Execute multimodal grounded RAG query",
          parameters: {},
        },
      ];
      const el = renderMcpToolsPanel(tools);
      expect(el.textContent).toContain("query_irdai_policy");
    });
  });

  describe("renderInspector", () => {
    it("renders default placeholder when citation is null", () => {
      const el = renderInspector(null);
      expect(el.textContent).toContain("Click any citation chip");
    });

    it("renders 200-DPI visual table crop and parent context when citation is present", () => {
      const citation: GroundedCitation = {
        citation_id: "cit_01",
        doc_id: "arogya",
        policy_name: "Arogya Sanjeevani",
        page_number: 2,
        section_type: "SCHEDULE_OF_BENEFITS",
        section_title: "Table of Benefits",
        clause_code: "Excl02",
        parent_id: "par_01",
        child_chunk_id: "chk_01",
        chunk_type: "TABLE",
        verbatim_quote: "Cataract per eye up to ₹40,000.",
        parent_context_preview: "Full Parent Section Context Text Here",
        image_crop_url: "/api/v1/crops/test_table.png",
        relevance_score: 0.92,
      };
      const el = renderInspector(citation);
      const img = el.querySelector("img#crop-image") as HTMLImageElement | null;
      expect(img).not.toBeNull();
      expect(img?.getAttribute("src")).toBe("/api/v1/crops/test_table.png");
      expect(el.textContent).toContain("Cataract per eye up to ₹40,000.");
      expect(el.textContent).toContain("Full Parent Section Context Text Here");
    });
  });
});
