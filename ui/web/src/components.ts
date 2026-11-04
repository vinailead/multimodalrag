/**
 * Modular Google Material Design 3 UI component renderers.
 */

import type {
  FinOpsSummary,
  GroundedCitation,
  McpToolDefinition,
  PolicyCoverageSummary,
  QueryIntentClassification,
  RAGTriadScorecard,
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
