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
        recommended: true,
        headline: "Smart Portfolio Split Recommended",
        rationale: "Splitting saves money.",
        single_floater_doc_id: "hdfc_ergo_optima_secure",
        single_floater_annual_inr: 46000,
        young_family_doc_id: "hdfc_ergo_optima_secure",
        young_family_policy_name: "HDFC ERGO Optima Secure",
        young_family_annual_inr: 15000,
        parents_doc_id: "bajaj_allianz_health_guard",
        parents_policy_name: "Bajaj Allianz Health Guard",
        parents_annual_inr: 24000,
        combined_split_annual_inr: 39000,
        annual_savings_inr: 7000,
      });
      expect(el.textContent).toContain("Smart Portfolio Split Recommended");
      expect(el.textContent).toContain("7,000");
    });

    it("renders full advisor recommendation view including cards, matrix, and claim simulator", () => {
      const mockRec: AdvisorRecommendationResponse = {
        extracted_profile: {
          primary_age: 26,
          eldest_member_age: 26,
          family_size: 5,
          includes_parents: true,
          parents_eldest_age: 56,
          smoker: false,
          drinker: false,
          has_pre_existing_diseases: false,
          pre_existing_conditions: [],
          maternity_needed: false,
          city_tier: "TIER_1_METRO",
          target_sum_insured_inr: 1000000,
          budget_priority: "BALANCED",
        },
        profile_completeness_pct: 100,
        needs_more_info: false,
        probing_questions: [
          {
            question_id: "probe_parents",
            slot_name: "includes_parents",
            question_text: "Parents included?",
            why_it_matters: "Age band",
            options: ["Yes"],
          },
        ],
        portfolio_split_analysis: {
          recommended: true,
          headline: "Split Recommended",
          rationale: "Saves premium",
          single_floater_doc_id: "hdfc_ergo_optima_secure",
          single_floater_annual_inr: 45000,
          young_family_doc_id: "hdfc_ergo_optima_secure",
          young_family_policy_name: "HDFC ERGO Optima Secure",
          young_family_annual_inr: 14000,
          parents_doc_id: "bajaj_allianz_health_guard",
          parents_policy_name: "Bajaj Allianz Health Guard",
          parents_annual_inr: 22000,
          combined_split_annual_inr: 36000,
          annual_savings_inr: 9000,
        },
        recommendations: [
          {
            rank: 1,
            match_score_pct: 96.5,
            badge_label: "Best Overall Fit",
            policy: {
              doc_id: "hdfc_ergo_optima_secure",
              policy_name: "HDFC ERGO Optima Secure",
              insurer_name: "HDFC ERGO",
              uin: "HDFHLIP25041V062425",
              product_type: "HEALTH_INDIVIDUAL_FLOATER",
              positioning_tier: "ULTRA_COMPREHENSIVE",
              eligible_sum_insured_options_inr: [1000000],
              default_sum_insured_inr: 1000000,
              room_rent_limit: "No Cap (Any Room)",
              room_rent_capped: false,
              room_rent_max_pct_per_day: null,
              room_rent_max_inr_per_day: null,
              cataract_limit: "Up to 100% SI",
              cataract_max_per_eye_inr: null,
              ped_waiting_months: 36,
              specific_disease_waiting_months: 24,
              initial_waiting_days: 30,
              mandatory_copay_pct: 0,
              restoration_benefit: "100% Restore",
              no_claim_bonus: "50% per yr",
              consumables_covered: true,
              maternity_covered: false,
              ayush_coverage: "100% SI",
              day_care_procedures: "All",
              modern_treatments_coverage: "100% SI",
              key_highlights: ["4X Cover"],
              watch_outs: ["No maternity"],
              feature_citations: {},
            },
            premium: {
              doc_id: "hdfc_ergo_optima_secure",
              policy_name: "HDFC ERGO Optima Secure",
              sum_insured_inr: 1000000,
              eldest_age_used: 26,
              family_size_used: 5,
              base_annual_premium_inr: 9800,
              family_floater_load_inr: 6664,
              healthy_lifestyle_discount_inr: 1235,
              subtotal_before_gst_inr: 15229,
              gst_18_pct_inr: 2741,
              total_annual_premium_inr: 17970,
              monthly_emi_inr: 1542,
              pricing_notes: ["7.5% discount"],
            },
            why_this_fits: ["Zero room rent cap"],
            trade_offs: ["No maternity"],
          },
        ],
        comparison_matrix: {
          compared_policies: [
            {
              doc_id: "hdfc_ergo_optima_secure",
              policy_name: "HDFC ERGO Optima Secure",
              insurer_name: "HDFC ERGO",
              uin: "HDFHLIP25041V062425",
              product_type: "HEALTH_INDIVIDUAL_FLOATER",
              positioning_tier: "ULTRA_COMPREHENSIVE",
              eligible_sum_insured_options_inr: [1000000],
              default_sum_insured_inr: 1000000,
              room_rent_limit: "No Cap",
              room_rent_capped: false,
              room_rent_max_pct_per_day: null,
              room_rent_max_inr_per_day: null,
              cataract_limit: "No Cap",
              cataract_max_per_eye_inr: null,
              ped_waiting_months: 36,
              specific_disease_waiting_months: 24,
              initial_waiting_days: 30,
              mandatory_copay_pct: 0,
              restoration_benefit: "100%",
              no_claim_bonus: "50%",
              consumables_covered: true,
              maternity_covered: false,
              ayush_coverage: "100%",
              day_care_procedures: "All",
              modern_treatments_coverage: "100%",
              key_highlights: [],
              watch_outs: [],
              feature_citations: {},
            },
          ],
          premiums: {},
          comparison_rows: [
            {
              parameter_key: "room_rent_limit",
              parameter_label: "Daily Room Rent & ICU Cap",
              category: "Hospitalization Limits",
              cells: [
                {
                  doc_id: "hdfc_ergo_optima_secure",
                  policy_name: "HDFC ERGO Optima Secure",
                  display_value: "No Cap (Any Room)",
                  is_best_in_class: true,
                  sentiment: "POSITIVE",
                  citation: {
                    doc_id: "hdfc_ergo_optima_secure",
                    policy_name: "HDFC ERGO Optima Secure",
                    section_title: "Schedule of Benefits",
                    clause_code: null,
                    page_number: 2,
                    verbatim_quote: "No cap on room rent.",
                  },
                },
              ],
            },
          ],
          claim_simulation: {
            scenario_title: "₹2,50,000 Hospitalization",
            hospital_bill_inr: 250000,
            room_rent_per_day_inr: 9000,
            stay_days: 4,
            is_cataract: false,
            results: [
              {
                doc_id: "hdfc_ergo_optima_secure",
                policy_name: "HDFC ERGO Optima Secure",
                hospital_bill_inr: 250000,
                room_rent_deduction_inr: 0,
                sub_limit_deduction_inr: 0,
                consumables_deduction_inr: 0,
                copay_deduction_inr: 0,
                insurer_payable_inr: 250000,
                out_of_pocket_inr: 0,
                explanation: "Zero out-of-pocket.",
              },
            ],
          },
          executive_verdict: "HDFC ERGO wins.",
        },
        advisory_summary: "HDFC ERGO Optima Secure is #1.",
        irdai_disclaimer: "Indicative rates.",
      };

      const el = renderAdvisorRecommendation(mockRec);
      expect(el.textContent).toContain("HDFC ERGO Optima Secure");
      expect(el.textContent).toContain("17,970");
      expect(el.textContent).toContain("Zero out-of-pocket.");
      expect(el.querySelector("#comparison-matrix-table")).not.toBeNull();
      expect(el.querySelector("#claim-simulation-card")).not.toBeNull();
      expect(renderRecommendationCards(mockRec.recommendations).textContent).toContain("96.5%");
      expect(renderComparisonMatrix(mockRec.comparison_matrix).textContent).toContain("★ Best");
      expect(
        renderClaimSimulation(mockRec.comparison_matrix.claim_simulation).textContent,
      ).toContain("2,50,000");
    });
  });
});
