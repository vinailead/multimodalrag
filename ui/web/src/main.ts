/**
 * Indian Insurance Multimodal RAG — Application Bootstrap & Event Controller.
 */

import {
  fetchBenchmarkScorecard,
  fetchFinOps,
  fetchHealth,
  fetchMcpTools,
  fetchPolicies,
  submitQuery,
} from "./api.ts";
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
} from "./components.ts";
import type { GroundedCitation, GroundedQueryResponse } from "./types.ts";

export async function initApp(): Promise<void> {
  const policySelect = document.getElementById("policy-select") as HTMLSelectElement | null;
  const finopsContainer = document.getElementById("finops-container");
  const scorecardContainer = document.getElementById("scorecard-container");
  const mcpContainer = document.getElementById("mcp-container");
  const queryInput = document.getElementById("query-input") as HTMLInputElement | null;
  const submitBtn = document.getElementById("query-submit-btn") as HTMLButtonElement | null;
  const samplePills = document.querySelectorAll(".m3-pill");

  const piiBanner = document.getElementById("pii-banner");
  const piiDetails = document.getElementById("pii-details");
  const intentContainer = document.getElementById("intent-container");
  const precedenceBanner = document.getElementById("precedence-banner");
  const precedenceText = document.getElementById("precedence-text");
  const abstentionBanner = document.getElementById("abstention-banner");
  const abstentionReason = document.getElementById("abstention-reason");
  const answerCard = document.getElementById("answer-card");
  const answerText = document.getElementById("answer-text");
  const confidenceSlot = document.getElementById("confidence-slot");
  const breakdownSlot = document.getElementById("breakdown-slot");
  const citationsSlot = document.getElementById("citations-slot");
  const waterfallSlot = document.getElementById("waterfall-slot");
  const inspectorContent = document.getElementById("inspector-content");

  // 1. Initial Data Fetch
  try {
    const health = await fetchHealth();
    const healthBadge = document.getElementById("health-badge");
    if (healthBadge) {
      healthBadge.textContent = `Backend: ${health.status.toUpperCase()} (v${health.version})`;
    }
  } catch {
    // Backend offline / mock mode
  }

  try {
    const policies = await fetchPolicies();
    if (policySelect && policies.length > 0) {
      policySelect.innerHTML = "";
      for (const p of policies) {
        const opt = document.createElement("option");
        opt.value = p.doc_id;
        opt.textContent = `${p.policy_name} (${p.uin})`;
        policySelect.appendChild(opt);
      }
    }
  } catch {
    // Ignore fetch error in stub mode
  }

  try {
    const finops = await fetchFinOps();
    if (finopsContainer) {
      finopsContainer.innerHTML = "";
      finopsContainer.appendChild(renderFinOpsPanel(finops));
    }
  } catch {
    // Ignore
  }

  try {
    const scorecard = await fetchBenchmarkScorecard();
    if (scorecardContainer) {
      scorecardContainer.innerHTML = "";
      scorecardContainer.appendChild(renderScorecardPanel(scorecard));
    }
  } catch {
    // Ignore
  }

  try {
    const mcpTools = await fetchMcpTools();
    if (mcpContainer) {
      mcpContainer.innerHTML = "";
      mcpContainer.appendChild(renderMcpToolsPanel(mcpTools));
    }
  } catch {
    // Ignore
  }

  // 2. Wire Sample Query Pills
  samplePills.forEach((pill) => {
    pill.addEventListener("click", () => {
      const q = pill.getAttribute("data-query");
      if (q && queryInput) {
        queryInput.value = q;
        queryInput.focus();
      }
    });
  });

  // 3. Query Submission Handler
  const handleQuery = async (): Promise<void> => {
    const query = queryInput?.value.trim();
    if (!query) return;

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Analyzing...";
    }

    try {
      const docId = policySelect?.value || undefined;
      const resp: GroundedQueryResponse = await submitQuery(query, docId);

      // Handle DPDP PII Banner
      if (piiBanner && piiDetails) {
        if (resp.pii_redactions_applied.length > 0) {
          piiBanner.classList.remove("hidden");
          piiDetails.textContent = `DPDP Act 2023 Masking applied to: ${resp.pii_redactions_applied.join(", ")}`;
        } else {
          piiBanner.classList.add("hidden");
        }
      }

      // Handle Intent Card
      if (intentContainer) {
        intentContainer.innerHTML = "";
        intentContainer.appendChild(renderIntentChips(resp.intent));
        intentContainer.classList.remove("hidden");
      }

      // Handle Precedence Banner
      if (precedenceBanner && precedenceText) {
        precedenceBanner.classList.remove("hidden");
        precedenceText.textContent = `${resp.precedence_check.rule_applied} — ${resp.precedence_check.note}`;
      }

      // Handle Answer Card & Abstention
      if (answerCard) answerCard.classList.remove("hidden");
      if (confidenceSlot) {
        confidenceSlot.innerHTML = "";
        confidenceSlot.appendChild(renderConfidenceBadge(resp.confidence_score, resp.abstained));
      }

      if (abstentionBanner && abstentionReason) {
        if (resp.abstained) {
          abstentionBanner.classList.remove("hidden");
          abstentionReason.textContent =
            resp.abstention_reason ??
            "Confidence is below 0.70 threshold. In accordance with IRDAI guidance, indeterminate claims cannot be confirmed without explicit underwriter verification.";
        } else {
          abstentionBanner.classList.add("hidden");
        }
      }

      if (answerText) {
        answerText.textContent = resp.answer;
      }

      // Handle Structured Breakdown
      if (breakdownSlot) {
        breakdownSlot.innerHTML = "";
        breakdownSlot.appendChild(renderPolicyBreakdown(resp.coverage_summary));
      }

      // Handle Citations
      if (citationsSlot) {
        citationsSlot.innerHTML = "";
        const onSelectCitation = (citation: GroundedCitation): void => {
          if (inspectorContent) {
            inspectorContent.innerHTML = "";
            inspectorContent.appendChild(renderInspector(citation));
          }
        };
        citationsSlot.appendChild(renderCitationChips(resp.citations, onSelectCitation));

        // Auto-select first citation in inspector if present
        if (resp.citations.length > 0 && inspectorContent) {
          inspectorContent.innerHTML = "";
          inspectorContent.appendChild(renderInspector(resp.citations[0]));
        }
      }

      // Handle OpenTelemetry Execution Waterfall
      if (waterfallSlot) {
        waterfallSlot.innerHTML = "";
        waterfallSlot.appendChild(renderTraceWaterfall(resp.trace_spans));
      }

      // Refresh FinOps Panel
      try {
        const finops = await fetchFinOps();
        if (finopsContainer) {
          finopsContainer.innerHTML = "";
          finopsContainer.appendChild(renderFinOpsPanel(finops));
        }
      } catch {
        // Ignore
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(`Query failed: ${msg}`);
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Ask";
      }
    }
  };

  submitBtn?.addEventListener("click", () => {
    void handleQuery();
  });

  queryInput?.addEventListener("keydown", (e: KeyboardEvent) => {
    if (e.key === "Enter") {
      void handleQuery();
    }
  });
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  window.addEventListener("DOMContentLoaded", () => {
    void initApp();
  });
}
