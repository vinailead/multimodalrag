/**
 * Modular Google Material Design 3 UI component renderers.
 */

import type {
  AdvisorRecommendationResponse,
  ClaimSimulationResponse,
  FinOpsSummary,
  GroundedCitation,
  McpToolDefinition,
  PolicyComparisonResponse,
  PolicyCoverageSummary,
  PortfolioSplitOption,
  ProbingQuestion,
  QueryIntentClassification,
  RAGTriadScorecard,
  RankedPolicyRecommendation,
  TraceSpan,
} from "./types.ts";

export function renderConfidenceBadge(score: number, abstained: boolean): HTMLElement {
  const badge = document.createElement("span");
  badge.id = "confidence-badge";
  badge.className = "m3-badge";

  if (abstained || score < 0.7) {
    badge.classList.add("m3-badge-error");
    badge.textContent = `Confidence: ${(score * 100).toFixed(1)}% (Abstained)`;
    badge.setAttribute("aria-label", "Low confidence abstained");
  } else {
    badge.classList.add("m3-badge-verified");
    badge.textContent = `Confidence: ${(score * 100).toFixed(1)}% (Verified)`;
    badge.setAttribute("aria-label", "High confidence grounded answer");
  }
  return badge;
}

export function renderIntentChips(intent: QueryIntentClassification): HTMLElement {
  const container = document.createElement("div");
  container.className = "m3-pills-row";

  // Primary Section Chip
  const primaryChip = document.createElement("span");
  primaryChip.className = "m3-badge m3-badge-primary";
  primaryChip.textContent = `Intent: ${intent.primary_section}`;
  container.appendChild(primaryChip);

  // Sub-queries (CRAG Decomposition)
  for (const sq of intent.sub_queries) {
    const chip = document.createElement("span");
    chip.className = "m3-pill";
    chip.textContent = `CRAG Sub-query: ${sq}`;
    container.appendChild(chip);
  }

  // Model Escalation Badge
  const modelChip = document.createElement("span");
  modelChip.className = intent.requires_pro_escalation
    ? "m3-badge m3-badge-warning"
    : "m3-badge m3-badge-primary";
  modelChip.textContent = intent.requires_pro_escalation
    ? "Model: Gemini 2.5 Pro (Escalated)"
    : "Model: Gemini 2.5 Flash";
  container.appendChild(modelChip);

  return container;
}

export function renderPolicyBreakdown(summary: PolicyCoverageSummary): HTMLElement {
  const table = document.createElement("table");
  table.className = "m3-breakdown-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>Coverage Dimension</th>
        <th>IRDAI Policy Determination</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Coverage Status</strong></td>
        <td><span class="m3-badge ${summary.coverage_status === "INDETERMINATE" ? "m3-badge-error" : "m3-badge-verified"}">${summary.coverage_status}</span></td>
      </tr>
      <tr>
        <td><strong>Waiting Period</strong></td>
        <td>${escapeHtml(summary.waiting_period_details)}</td>
      </tr>
      <tr>
        <td><strong>Sub-Limits / Cap</strong></td>
        <td>${escapeHtml(summary.applicable_sub_limits)}</td>
      </tr>
      <tr>
        <td><strong>Cost Sharing / Co-Pay</strong></td>
        <td>${escapeHtml(summary.cost_sharing_or_deductible)}</td>
      </tr>
      <tr>
        <td><strong>Applicable Exclusions</strong></td>
        <td>${summary.applicable_exclusions.length > 0 ? summary.applicable_exclusions.map((c) => `<code style="font-family: monospace; background: #e9eef6; padding: 2px 6px; border-radius: 4px; margin-right: 4px;">${escapeHtml(c)}</code>`).join("") : "None specified"}</td>
      </tr>
    </tbody>
  `;
  return table;
}

export function renderCitationChips(
  citations: GroundedCitation[],
  onSelect: (citation: GroundedCitation) => void,
): HTMLElement {
  const container = document.createElement("div");
  container.className = "m3-pills-row";

  if (citations.length === 0) {
    const emptyNotice = document.createElement("span");
    emptyNotice.style.fontSize = "13px";
    emptyNotice.style.color = "var(--md-sys-color-on-surface-variant)";
    emptyNotice.textContent = "No citations available for this response.";
    container.appendChild(emptyNotice);
    return container;
  }

  citations.forEach((cit, index) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "m3-citation-chip";
    chip.setAttribute("data-testid", `citation-chip-${index}`);
    chip.setAttribute(
      "aria-label",
      `Citation ${index + 1}: Page ${cit.page_number}, ${cit.section_title}`,
    );

    const icon = cit.image_crop_url ? "📊" : "📄";
    const label = cit.clause_code ? `[${cit.clause_code}]` : `[Page ${cit.page_number}]`;
    chip.textContent = `${icon} ${label} ${cit.section_title.substring(0, 24)}...`;

    chip.addEventListener("click", () => {
      container.querySelectorAll(".m3-citation-chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      onSelect(cit);
    });

    container.appendChild(chip);
  });

  return container;
}

export function renderTraceWaterfall(spans: TraceSpan[]): HTMLElement {
  const container = document.createElement("div");
  container.className = "m3-card";

  const title = document.createElement("div");
  title.className = "m3-card-title";
  title.innerHTML = "<span>OpenTelemetry Execution Waterfall</span><span>Duration</span>";
  container.appendChild(title);

  if (spans.length === 0) {
    const empty = document.createElement("p");
    empty.style.fontSize = "12px";
    empty.style.color = "var(--md-sys-color-on-surface-variant)";
    empty.textContent = "No spans recorded.";
    container.appendChild(empty);
    return container;
  }

  const maxDuration = Math.max(...spans.map((s) => s.start_offset_ms + s.duration_ms), 1);

  for (const span of spans) {
    const row = document.createElement("div");
    row.className = "m3-waterfall-row";

    const nameCol = document.createElement("div");
    nameCol.className = "m3-waterfall-name";
    nameCol.textContent = span.name;
    nameCol.title = span.name;

    const trackCol = document.createElement("div");
    trackCol.className = "m3-waterfall-track";

    const bar = document.createElement("div");
    bar.className = "m3-waterfall-bar";
    const leftPct = Math.min(95, (span.start_offset_ms / maxDuration) * 100);
    const widthPct = Math.max(3, (span.duration_ms / maxDuration) * 100);
    bar.style.marginLeft = `${leftPct.toFixed(1)}%`;
    bar.style.width = `${widthPct.toFixed(1)}%`;
    trackCol.appendChild(bar);

    const durCol = document.createElement("div");
    durCol.className = "m3-waterfall-duration";
    durCol.textContent = `${span.duration_ms.toFixed(1)}ms`;

    row.appendChild(nameCol);
    row.appendChild(trackCol);
    row.appendChild(durCol);
    container.appendChild(row);
  }

  return container;
}

export function renderFinOpsPanel(finops: FinOpsSummary): HTMLElement {
  const container = document.createElement("div");
  container.className = "m3-stat-grid";

  container.innerHTML = `
    <div class="m3-stat-item">
      <div class="m3-stat-label">Total Spend (USD)</div>
      <div class="m3-stat-value">$${finops.total_cost_usd.toFixed(4)}</div>
    </div>
    <div class="m3-stat-item">
      <div class="m3-stat-label">Total Spend (INR)</div>
      <div class="m3-stat-value">₹${finops.total_cost_inr.toFixed(2)}</div>
    </div>
    <div class="m3-stat-item">
      <div class="m3-stat-label">Cache Hit Rate</div>
      <div class="m3-stat-value">${finops.cache_hit_rate_pct.toFixed(1)}%</div>
    </div>
    <div class="m3-stat-item">
      <div class="m3-stat-label">Budget Utilized</div>
      <div class="m3-stat-value">${finops.budget_utilized_pct.toFixed(1)}%</div>
    </div>
  `;
  return container;
}

export function renderScorecardPanel(scorecard: RAGTriadScorecard): HTMLElement {
  const container = document.createElement("div");
  container.className = "m3-stat-grid";

  container.innerHTML = `
    <div class="m3-stat-item">
      <div class="m3-stat-label">Context Recall @ k</div>
      <div class="m3-stat-value">${(scorecard.context_recall_at_k * 100).toFixed(1)}%</div>
    </div>
    <div class="m3-stat-item">
      <div class="m3-stat-label">Faithfulness</div>
      <div class="m3-stat-value">${(scorecard.answer_faithfulness * 100).toFixed(1)}%</div>
    </div>
    <div class="m3-stat-item">
      <div class="m3-stat-label">Abstention F1</div>
      <div class="m3-stat-value">${(scorecard.abstention_f1 * 100).toFixed(1)}%</div>
    </div>
    <div class="m3-stat-item">
      <div class="m3-stat-label">Table Numerical Exact</div>
      <div class="m3-stat-value">${(scorecard.table_numerical_exactness * 100).toFixed(1)}%</div>
    </div>
  `;
  return container;
}

export function renderMcpToolsPanel(tools: McpToolDefinition[]): HTMLElement {
  const container = document.createElement("div");
  container.style.display = "flex";
  container.style.flexDirection = "column";
  container.style.gap = "6px";

  for (const t of tools) {
    const item = document.createElement("div");
    item.style.fontSize = "12px";
    item.style.padding = "6px 8px";
    item.style.background = "var(--md-sys-color-surface-container-low)";
    item.style.borderRadius = "var(--md-sys-shape-corner-small)";
    item.innerHTML = `<strong><code>${escapeHtml(t.name)}</code></strong>: <span style="color: var(--md-sys-color-on-surface-variant);">${escapeHtml(t.description.substring(0, 60))}...</span>`;
    container.appendChild(item);
  }
  return container;
}

export function renderInspector(citation: GroundedCitation | null): HTMLElement {
  const container = document.createElement("div");

  if (!citation) {
    container.innerHTML = `
      <p style="font-size: 13px; color: var(--md-sys-color-on-surface-variant);">
        Click any citation chip in the center workspace to inspect the 200-DPI visual table crop, full parent clause context, and 1-hop cross-references.
      </p>
    `;
    return container;
  }

  const imageSection = citation.image_crop_url
    ? `
      <div style="margin-bottom: 12px;">
        <div style="font-size: 12px; font-weight: 600; color: var(--md-sys-color-on-surface-variant); margin-bottom: 6px;">
          200-DPI Visual Table Snapshot (Page ${citation.page_number})
        </div>
        <img id="crop-image" src="${escapeHtml(citation.image_crop_url)}" alt="Visual Table Crop Page ${citation.page_number}" class="m3-crop-img" />
      </div>
    `
    : `
      <div style="font-size: 12px; color: var(--md-sys-color-on-surface-variant); margin-bottom: 12px;">
        <em>Text Section (No tabular crop for this clause)</em>
      </div>
    `;

  container.innerHTML = `
    ${imageSection}
    <div style="margin-bottom: 12px;">
      <div style="font-size: 12px; font-weight: 600; color: var(--md-sys-color-on-surface-variant); margin-bottom: 4px;">
        Verbatim Cited Clause:
      </div>
      <div class="m3-quote-box">"${escapeHtml(citation.verbatim_quote)}"</div>
    </div>
    <div style="margin-bottom: 12px;">
      <div style="font-size: 12px; font-weight: 600; color: var(--md-sys-color-on-surface-variant); margin-bottom: 4px;">
        Parent Section Context (${escapeHtml(citation.section_title)}):
      </div>
      <div class="m3-parent-preview" id="inspector-parent-text">${escapeHtml(citation.parent_context_preview)}</div>
    </div>
    <div>
      <div style="font-size: 12px; font-weight: 600; color: var(--md-sys-color-on-surface-variant); margin-bottom: 4px;">
        Metadata & Precedence:
      </div>
      <div style="font-size: 11px; font-family: 'Roboto Mono', monospace; color: var(--md-sys-color-on-surface-variant);">
        Doc ID: ${escapeHtml(citation.doc_id)}<br/>
        Parent ID: ${escapeHtml(citation.parent_id)}<br/>
        Child ID: ${escapeHtml(citation.child_chunk_id)}<br/>
        Relevance Score: ${citation.relevance_score.toFixed(4)}
      </div>
    </div>
  `;

  return container;
}

export function renderProbingQuestions(
  questions: ProbingQuestion[],
  onSelectOption?: (slotName: string, optionText: string) => void,
): HTMLElement {
  const container = document.createElement("div");
  container.className = "m3-card";
  container.id = "probing-questions-card";

  const header = document.createElement("div");
  header.className = "m3-card-title";
  header.innerHTML = `<span>🧭 Smart Follow-Up Questions (Needs-Discovery Probing)</span><span class="m3-badge m3-badge-warning">${questions.length} Slots Needed</span>`;
  container.appendChild(header);

  for (const q of questions) {
    const qBlock = document.createElement("div");
    qBlock.className = "m3-probe-block";
    qBlock.style.marginBottom = "12px";
    qBlock.style.padding = "10px 12px";
    qBlock.style.background = "var(--md-sys-color-surface-container-low)";
    qBlock.style.borderRadius = "var(--md-sys-shape-corner-small)";

    const qTitle = document.createElement("div");
    qTitle.style.fontWeight = "600";
    qTitle.style.fontSize = "13px";
    qTitle.style.marginBottom = "4px";
    qTitle.textContent = q.question_text;

    const qWhy = document.createElement("div");
    qWhy.style.fontSize = "11px";
    qWhy.style.color = "var(--md-sys-color-on-surface-variant)";
    qWhy.style.marginBottom = "8px";
    qWhy.textContent = `Why it matters: ${q.why_it_matters}`;

    const optsRow = document.createElement("div");
    optsRow.className = "m3-pills-row";
    q.options.forEach((opt, idx) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "m3-pill m3-probe-option";
      btn.setAttribute("data-probe-slot", q.slot_name);
      btn.setAttribute("data-probe-option", opt);
      btn.setAttribute("data-testid", `probe-${q.question_id}-${idx}`);
      btn.textContent = opt;
      btn.addEventListener("click", () => {
        optsRow
          .querySelectorAll(".m3-probe-option")
          .forEach((el) => el.classList.remove("m3-badge-primary"));
        btn.classList.add("m3-badge-primary");
        if (onSelectOption) {
          onSelectOption(q.slot_name, opt);
        }
      });
      optsRow.appendChild(btn);
    });

    qBlock.appendChild(qTitle);
    qBlock.appendChild(qWhy);
    qBlock.appendChild(optsRow);
    container.appendChild(qBlock);
  }

  return container;
}

export function renderPortfolioSplitBanner(split: PortfolioSplitOption): HTMLElement {
  const banner = document.createElement("div");
  banner.id = "portfolio-split-banner";
  banner.className = "m3-banner m3-banner-verified";
  banner.style.flexDirection = "column";
  banner.innerHTML = `
    <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
      <strong>💡 ${escapeHtml(split.headline)}</strong>
      <span class="m3-badge m3-badge-verified">Save ₹${split.annual_savings_inr.toLocaleString("en-IN")}/yr</span>
    </div>
    <p style="font-size: 13px; margin-top: 4px;">${escapeHtml(split.rationale)}</p>
    <div class="m3-stat-grid" style="width: 100%; margin-top: 8px; grid-template-columns: repeat(3, 1fr);">
      <div class="m3-stat-item">
        <div class="m3-stat-label">Single Floater (All Together)</div>
        <div class="m3-stat-value">₹${split.single_floater_annual_inr.toLocaleString("en-IN")}/yr</div>
      </div>
      <div class="m3-stat-item">
        <div class="m3-stat-label">Split 1: ${escapeHtml(split.young_family_policy_name)}</div>
        <div class="m3-stat-value">₹${split.young_family_annual_inr.toLocaleString("en-IN")}/yr</div>
      </div>
      <div class="m3-stat-item">
        <div class="m3-stat-label">Split 2: ${escapeHtml(split.parents_policy_name)}</div>
        <div class="m3-stat-value">₹${split.parents_annual_inr.toLocaleString("en-IN")}/yr</div>
      </div>
    </div>
  `;
  return banner;
}

export function renderRecommendationCards(
  recommendations: RankedPolicyRecommendation[],
): HTMLElement {
  const container = document.createElement("div");
  container.id = "advisor-recommendations-grid";
  container.style.display = "flex";
  container.style.flexDirection = "column";
  container.style.gap = "12px";

  for (const rec of recommendations) {
    const card = document.createElement("div");
    card.className = "m3-card";
    card.setAttribute("data-testid", `rec-card-${rec.rank}`);

    const highlightsHtml = rec.why_this_fits
      .map((w) => `<li style="margin-left: 16px; font-size: 13px;">✅ ${escapeHtml(w)}</li>`)
      .join("");
    const tradeOffsHtml = rec.trade_offs
      .map(
        (t) =>
          `<li style="margin-left: 16px; font-size: 12px; color: var(--md-sys-color-warning-text);">⚠️ ${escapeHtml(t)}</li>`,
      )
      .join("");

    card.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; flex-wrap: wrap; gap: 8px;">
        <div>
          <span class="m3-badge m3-badge-primary" style="margin-right: 6px;">#${rec.rank} ${escapeHtml(rec.badge_label)}</span>
          <strong style="font-size: 16px;">${escapeHtml(rec.policy.policy_name)}</strong>
          <div style="font-size: 11px; color: var(--md-sys-color-on-surface-variant);">
            ${escapeHtml(rec.policy.insurer_name)} · UIN: ${escapeHtml(rec.policy.uin)}
          </div>
        </div>
        <div style="text-align: right;">
          <span class="m3-badge m3-badge-verified">Match: ${rec.match_score_pct.toFixed(1)}%</span>
          <div style="font-size: 16px; font-weight: 700; color: var(--md-sys-color-primary); margin-top: 2px;">
            ₹${rec.premium.total_annual_premium_inr.toLocaleString("en-IN")}/yr
            <span style="font-size: 12px; font-weight: 500; color: var(--md-sys-color-on-surface-variant);">
              (₹${rec.premium.monthly_emi_inr.toLocaleString("en-IN")}/mo incl. 18% GST)
            </span>
          </div>
        </div>
      </div>
      <div class="m3-stat-grid" style="grid-template-columns: repeat(4, 1fr); margin-bottom: 10px;">
        <div class="m3-stat-item">
          <div class="m3-stat-label">Room Rent</div>
          <div class="m3-stat-value" style="font-size: 12px;">${escapeHtml(rec.policy.room_rent_limit)}</div>
        </div>
        <div class="m3-stat-item">
          <div class="m3-stat-label">PED Waiting</div>
          <div class="m3-stat-value" style="font-size: 12px;">${rec.policy.ped_waiting_months} Months</div>
        </div>
        <div class="m3-stat-item">
          <div class="m3-stat-label">Co-Payment</div>
          <div class="m3-stat-value" style="font-size: 12px;">${rec.policy.mandatory_copay_pct}%</div>
        </div>
        <div class="m3-stat-item">
          <div class="m3-stat-label">Healthy Discount</div>
          <div class="m3-stat-value" style="font-size: 12px;">-₹${rec.premium.healthy_lifestyle_discount_inr.toLocaleString("en-IN")}</div>
        </div>
      </div>
      <ul style="list-style: none; margin-bottom: 6px;">${highlightsHtml}</ul>
      <ul style="list-style: none;">${tradeOffsHtml}</ul>
    `;
    container.appendChild(card);
  }

  return container;
}

export function renderComparisonMatrix(comp: PolicyComparisonResponse): HTMLElement {
  const wrapper = document.createElement("div");
  wrapper.className = "m3-card";
  wrapper.id = "comparison-matrix-card";
  wrapper.style.overflowX = "auto";

  const title = document.createElement("div");
  title.className = "m3-card-title";
  title.innerHTML = `<span>⚖️ Side-by-Side Policy Comparison Matrix (${comp.compared_policies.length} Policies)</span><span class="m3-badge m3-badge-primary">Clause-Cited</span>`;
  wrapper.appendChild(title);

  const verdict = document.createElement("p");
  verdict.style.fontSize = "13px";
  verdict.style.marginBottom = "12px";
  verdict.textContent = comp.executive_verdict;
  wrapper.appendChild(verdict);

  const table = document.createElement("table");
  table.className = "m3-breakdown-table";
  table.id = "comparison-matrix-table";

  const headerCells = comp.compared_policies
    .map(
      (p) =>
        `<th>${escapeHtml(p.policy_name)}<br/><span style="font-weight:400;font-size:10px;">${escapeHtml(p.uin)}</span></th>`,
    )
    .join("");

  const bodyRows = comp.comparison_rows
    .map((row) => {
      const cellsHtml = row.cells
        .map((c) => {
          const badge = c.is_best_in_class
            ? `<span class="m3-badge m3-badge-verified" style="font-size:10px;padding:1px 6px;margin-left:4px;">★ Best</span>`
            : "";
          const citText = c.citation
            ? `<div style="font-size:10px;color:var(--md-sys-color-on-surface-variant);">[Page ${c.citation.page_number}]</div>`
            : "";
          return `<td><strong>${escapeHtml(c.display_value)}</strong>${badge}${citText}</td>`;
        })
        .join("");
      return `<tr><td><strong>${escapeHtml(row.parameter_label)}</strong><div style="font-size:10px;color:var(--md-sys-color-on-surface-variant);">${escapeHtml(row.category)}</div></td>${cellsHtml}</tr>`;
    })
    .join("");

  table.innerHTML = `
    <thead>
      <tr>
        <th>Feature / IRDAI Parameter</th>
        ${headerCells}
      </tr>
    </thead>
    <tbody>
      ${bodyRows}
    </tbody>
  `;
  wrapper.appendChild(table);
  return wrapper;
}

export function renderClaimSimulation(sim: ClaimSimulationResponse): HTMLElement {
  const container = document.createElement("div");
  container.className = "m3-card";
  container.id = "claim-simulation-card";

  const title = document.createElement("div");
  title.className = "m3-card-title";
  title.innerHTML = `<span>🏥 Out-of-Pocket Hospital Bill Simulator: ${escapeHtml(sim.scenario_title)}</span><span class="m3-badge m3-badge-primary">Bill: ₹${sim.hospital_bill_inr.toLocaleString("en-IN")}</span>`;
  container.appendChild(title);

  const table = document.createElement("table");
  table.className = "m3-breakdown-table";

  const rowsHtml = sim.results
    .map(
      (r) => `
      <tr>
        <td><strong>${escapeHtml(r.policy_name)}</strong></td>
        <td style="color: var(--md-sys-color-verified-text); font-weight: 600;">₹${r.insurer_payable_inr.toLocaleString("en-IN")}</td>
        <td style="color: ${r.out_of_pocket_inr > 0 ? "var(--md-sys-color-error-text)" : "var(--md-sys-color-verified-text)"}; font-weight: 600;">
          ₹${r.out_of_pocket_inr.toLocaleString("en-IN")}
        </td>
        <td style="font-size: 12px;">${escapeHtml(r.explanation)}</td>
      </tr>
    `,
    )
    .join("");

  table.innerHTML = `
    <thead>
      <tr>
        <th>Policy</th>
        <th>Insurer Pays (₹)</th>
        <th>You Pay Out-of-Pocket (₹)</th>
        <th>Actuarial Deduction Breakdown</th>
      </tr>
    </thead>
    <tbody>
      ${rowsHtml}
    </tbody>
  `;

  container.appendChild(table);
  return container;
}

export function renderAdvisorRecommendation(
  rec: AdvisorRecommendationResponse,
  onSelectProbeOption?: (slotName: string, optionText: string) => void,
): HTMLElement {
  const root = document.createElement("div");
  root.id = "advisor-recommendation-view";
  root.style.display = "flex";
  root.style.flexDirection = "column";
  root.style.gap = "14px";

  // 1. Advisory Executive Summary Card
  const summaryCard = document.createElement("div");
  summaryCard.className = "m3-card";
  summaryCard.innerHTML = `
    <div class="m3-card-title">
      <span>🎯 Personalized Underwriting & Advisory Verdict</span>
      <span class="m3-badge m3-badge-verified">Profile Completeness: ${rec.profile_completeness_pct.toFixed(0)}%</span>
    </div>
    <p style="font-size: 14px; font-weight: 500; margin-bottom: 8px;">${escapeHtml(rec.advisory_summary)}</p>
    <div class="m3-pills-row">
      <span class="m3-pill">Age: ${rec.extracted_profile.primary_age} yrs</span>
      <span class="m3-pill">Family Size: ${rec.extracted_profile.family_size}</span>
      <span class="m3-pill">Smoker: ${rec.extracted_profile.smoker ? "Yes" : "No"}</span>
      <span class="m3-pill">Drinker: ${rec.extracted_profile.drinker ? "Yes" : "No"}</span>
      <span class="m3-pill">Target Cover: ₹${rec.extracted_profile.target_sum_insured_inr.toLocaleString("en-IN")}</span>
    </div>
  `;
  root.appendChild(summaryCard);

  // 2. Portfolio Split Alert (if applicable)
  if (rec.portfolio_split_analysis) {
    root.appendChild(renderPortfolioSplitBanner(rec.portfolio_split_analysis));
  }

  // 3. Interactive Probing Questions (if any slots missing or follow-ups available)
  if (rec.probing_questions.length > 0) {
    root.appendChild(renderProbingQuestions(rec.probing_questions, onSelectProbeOption));
  }

  // 4. Ranked Policy Recommendations with GST-inclusive Premiums
  root.appendChild(renderRecommendationCards(rec.recommendations));

  // 5. Side-by-Side Comparison Matrix
  root.appendChild(renderComparisonMatrix(rec.comparison_matrix));

  // 6. Out-of-Pocket Claim Simulation
  root.appendChild(renderClaimSimulation(rec.comparison_matrix.claim_simulation));

  return root;
}

function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  };
  return text.replace(/[&<>"']/g, (m) => map[m]);
}
