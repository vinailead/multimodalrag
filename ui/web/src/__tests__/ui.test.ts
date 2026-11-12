import { describe, expect, it, vi } from "vitest";
import {
  renderAdvisorRecommendation,
  renderCitationChips,
  renderClaimSimulation,
  renderComparisonMatrix,
  renderConfidenceBadge,
  renderFinOpsPanel,
  renderInspector,
  renderIntentChips,
  renderMcpToolsPanel,
  renderPolicyBreakdown,
  renderPortfolioSplitBanner,
  renderProbingQuestions,
  renderRecommendationCards,
  renderScorecardPanel,
  renderTraceWaterfall,
} from "../components.ts";
import type {
  AdvisorRecommendationResponse,
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

  describe("Advisor, Comparison & Claim Simulator Components", () => {
    it("renders probing questions and invokes callback when option clicked", () => {
      const cb = vi.fn();
      const el = renderProbingQuestions(
        [
          {
            question_id: "probe_parents",
            slot_name: "includes_parents",
            question_text: "Does your family of 5 include parents?",
            why_it_matters: "Family floater rates depend on eldest member age.",
            options: ["Yes — Parents aged 50–60", "No — Spouse & Kids only"],
          },
        ],
        cb,
      );
      expect(el.textContent).toContain("Does your family of 5 include parents?");
      const btn = el.querySelector('[data-testid="probe-probe_parents-0"]') as HTMLButtonElement;
      expect(btn).not.toBeNull();
      btn.click();
      expect(cb).toHaveBeenCalledWith("includes_parents", "Yes — Parents aged 50–60");
    });

    it("renders portfolio split banner with savings", () => {
      const el = renderPortfolioSplitBanner({
        recommended_strategy: "SPLIT_PORTFOLIO",
        headline: "Smart Portfolio Split Recommended",
        explanation: "Splitting saves money.",
        single_floater_annual_inr: 46000,
        split_young_floater_annual_inr: 15000,
        split_parents_floater_annual_inr: 24000,
        split_total_annual_inr: 39000,
        annual_savings_inr: 7000,
        combined_effective_cover_inr: 2000000,
        key_reasons_to_split: ["Avoids age jump"],
      });
      expect(el.textContent).toContain("Smart Portfolio Split Recommended");
      expect(el.textContent).toContain("7,000");
    });

    it("renders full advisor recommendation view including cards, matrix, and claim simulator", () => {
      const mockCard = {
        doc_id: "hdfc_ergo_optima_secure",
        policy_name: "HDFC ERGO Optima Secure",
        short_name: "Optima Secure",
        insurer_name: "HDFC ERGO",
        uin: "HDFHLIP25041V062425",
        policy_category: "comprehensive_flagship" as const,
        tagline: "4X Cover",
        sum_insured_options_inr: [1000000],
        day_1_cover_multiplier: 2.0,
        effective_cover_note: "2X from Day 1",
        room_rent_limit: "No Cap (Any Room)",
        has_room_rent_cap: false,
        max_room_rent_per_day_inr: null,
        room_rent_pct_of_si: null,
        proportionate_deduction_applies: false,
        icu_limit: "No Cap",
        ped_waiting_months: 36,
        specific_disease_waiting_months: 24,
        initial_waiting_days: 30,
        cataract_limit_description: "Up to 100% SI",
        cataract_max_per_eye_inr: null,
        mandatory_copay_pct: 0,
        consumables_covered: true,
        consumables_note: "Covered via Protect Benefit",
        restoration_benefit: "100% Restore",
        no_claim_bonus_note: "50% per yr",
        pre_post_hospitalization: "60 / 180 days",
        ayush_coverage: "100% SI",
        healthy_lifestyle_discount_pct: 7.5,
        key_strengths: ["4X Cover"],
        fine_print_warnings: ["36m PED"],
        best_for_persona: "Young families",
        feature_citations: {},
      };

      const mockRec: AdvisorRecommendationResponse = {
        query: "26yo non smoker family of 5",
        extracted_profile: {
          proposer_age: 26,
          eldest_member_age: 56,
          family_size: 5,
          includes_parents: true,
          is_smoker: false,
          is_drinker: false,
          has_pre_existing_diseases: false,
          pre_existing_conditions: [],
          city_tier: "tier_1",
          target_sum_insured_inr: 1000000,
          budget_priority: "value_balanced",
        },
        completeness_pct: 100,
        needs_probing: false,
        probing_questions: [
          {
            question_id: "probe_parents",
            slot_name: "includes_parents",
            question_text: "Parents included?",
            why_it_matters: "Age band",
            options: ["Yes"],
          },
        ],
        executive_advisory_summary: "HDFC ERGO Optima Secure is #1.",
        portfolio_split_advice: {
          recommended_strategy: "SPLIT_PORTFOLIO",
          headline: "Split Recommended",
          explanation: "Saves premium",
          single_floater_annual_inr: 45000,
          split_young_floater_annual_inr: 14000,
          split_parents_floater_annual_inr: 22000,
          split_total_annual_inr: 36000,
          annual_savings_inr: 9000,
          combined_effective_cover_inr: 2000000,
          key_reasons_to_split: ["Saves 9000"],
        },
        ranked_policies: [
          {
            rank: 1,
            badge: "Best Overall Fit",
            match_score: 96.5,
            coverage_score: 98,
            waiting_period_score: 90,
            room_rent_score: 100,
            value_score: 95,
            feature_card: mockCard,
            premium: {
              doc_id: "hdfc_ergo_optima_secure",
              policy_name: "HDFC ERGO Optima Secure",
              sum_insured_inr: 1000000,
              effective_day_1_cover_inr: 2000000,
              pricing_age_used: 26,
              member_count: 5,
              city_tier: "tier_1",
              base_annual_premium_inr: 9800,
              floater_member_load_inr: 6664,
              city_zone_adjustment_inr: 0,
              healthy_lifestyle_discount_inr: 1235,
              smoker_loading_inr: 0,
              net_premium_before_gst_inr: 15229,
              gst_18_pct_inr: 2741,
              total_annual_premium_inr: 17970,
              monthly_emi_inr: 1542,
              cost_per_lakh_cover_inr: 899,
              pricing_notes: ["7.5% discount"],
            },
            why_recommended_for_you: ["Zero room rent cap"],
            watch_out_for: ["36m PED waiting"],
          },
        ],
        comparison_matrix: [
          {
            parameter_key: "room_rent_limit",
            parameter_label: "Daily Room Rent & ICU Cap",
            consumer_tooltip: "Hospitalization Limits",
            cells: {
              hdfc_ergo_optima_secure: {
                doc_id: "hdfc_ergo_optima_secure",
                display_value: "No Cap (Any Room)",
                is_winner: true,
                sentiment: "positive",
                citation: {
                  doc_id: "hdfc_ergo_optima_secure",
                  section_type: "SCHEDULE_OF_BENEFITS",
                  clause_code: null,
                  page_number: 2,
                  verbatim_quote: "No cap on room rent.",
                },
              },
            },
          },
        ],
        claim_simulation: {
          scenario_title: "₹2,50,000 Hospitalization",
          procedure_type: "general",
          claimed_bill_inr: 250000,
          hospital_room_rent_per_day_inr: 9000,
          days_hospitalized: 4,
          sum_insured_inr: 1000000,
          results: [
            {
              doc_id: "hdfc_ergo_optima_secure",
              policy_name: "HDFC ERGO Optima Secure",
              short_name: "Optima Secure",
              claimed_bill_inr: 250000,
              room_rent_deduction_inr: 0,
              procedure_sublimit_deduction_inr: 0,
              consumables_deduction_inr: 0,
              copay_deduction_inr: 0,
              insurer_payable_inr: 250000,
              user_out_of_pocket_inr: 0,
              coverage_ratio_pct: 100.0,
              explanation: "Zero out-of-pocket.",
            },
          ],
        },
      };

      const el = renderAdvisorRecommendation(mockRec);
      expect(el.textContent).toContain("HDFC ERGO Optima Secure");
      expect(el.textContent).toContain("17,970");
      expect(el.textContent).toContain("Zero out-of-pocket.");
      expect(el.querySelector("#comparison-matrix-table")).not.toBeNull();
      expect(el.querySelector("#claim-simulation-card")).not.toBeNull();
      expect(renderRecommendationCards(mockRec.ranked_policies).textContent).toContain("96.5%");
      expect(
        renderComparisonMatrix({
          profile_used: mockRec.extracted_profile,
          compared_policies: [mockCard],
          premiums: {},
          comparison_rows: mockRec.comparison_matrix,
          claim_simulation: mockRec.claim_simulation,
          fiduciary_summary: "HDFC ERGO wins.",
        }).textContent,
      ).toContain("★ Best");
      expect(renderClaimSimulation(mockRec.claim_simulation).textContent).toContain("2,50,000");
    });
  });
});
