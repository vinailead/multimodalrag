"""Streamlit Enterprise Showcase Dashboard for Indian Insurance Multimodal RAG."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from insurance_mmrag.config import get_settings
from insurance_mmrag.ingestion.sample_policy_factory import (
    create_arogya_sanjeevani_pdf,
    create_saral_suraksha_bima_pdf,
)
from insurance_mmrag.pipeline import InsuranceMMRAGPipeline, create_default_pipeline
from insurance_mmrag.schemas import GroundedQueryResponse

st.set_page_config(
    page_title="Indian Insurance Multimodal RAG",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_cached_pipeline() -> InsuranceMMRAGPipeline:
    settings = get_settings()
    pipe = create_default_pipeline(settings=settings, use_stub=True)

    # Seed sample policies
    p1 = settings.raw_policies_dir / "arogya_sanjeevani_policy_wordings.pdf"
    if not p1.exists():
        create_arogya_sanjeevani_pdf(p1)
    pipe.ingest_pdf(p1, doc_id="arogya_sanjeevani_national")

    p2 = settings.raw_policies_dir / "saral_suraksha_bima.pdf"
    if not p2.exists():
        create_saral_suraksha_bima_pdf(p2)
    pipe.ingest_pdf(p2, doc_id="saral_suraksha_bima_hdfc")

    return pipe


pipeline = get_cached_pipeline()

# --- Sidebar: Policy Selector & Telemetry ---
st.sidebar.title("🛡️ IRDAI Multimodal RAG")
st.sidebar.caption("Gemini 2.5 Vision · Structure-Aware · DPDP Compliant")

docs = pipeline.get_indexed_documents()
policy_options = {doc.doc_id: f"{doc.policy_name} ({doc.uin})" for doc in docs.values()}
selected_doc_id = st.sidebar.selectbox(
    "Active Policy Document",
    options=list(policy_options.keys()),
    format_func=lambda x: policy_options.get(x, x),
)

st.sidebar.markdown("---")
st.sidebar.subheader("💰 Live FinOps Telemetry")
finops = pipeline.get_finops_summary()
col_f1, col_f2 = st.sidebar.columns(2)
col_f1.metric("Spend (USD)", f"${finops.total_cost_usd:.4f}")
col_f2.metric("Spend (INR)", f"₹{finops.total_cost_inr:.2f}")
st.sidebar.caption(
    f"Cache Hit Rate: **{finops.cache_hit_rate_pct:.1f}%** | Budget Used: **{finops.budget_utilized_pct:.1f}%**"
)

st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ Governance & Compliance")
st.sidebar.success("✅ DPDP Act 2023 Masking Active")
st.sidebar.success("✅ IRDAI Legal Precedence Enforced")
st.sidebar.info("🔒 Zero External Model Calls in Test Mode")

# --- Main Workspace ---
st.title("Indian Insurance Policy Multimodal RAG")
st.markdown(
    "Ask any question about exclusions, waiting periods (`Excl01` to `Excl18`), sub-limits, or benefit schedules. "
    "Powered by **Gemini 2.5 Vision table extraction**, **Parent-Child chunking**, and **OpenTelemetry waterfall execution tracing**."
)

# Sample Queries Row
st.markdown("##### 💡 Sample Inquiries:")
sample_queries = [
    "What is the waiting period for cataract surgery under this policy?",
    "What is the daily room rent sub-limit and mandatory co-payment percentage?",
    "What is the waiting period for Pre-Existing Diseases under Code-Excl01?",
    "Does this insurance policy cover pet veterinary dental implants in Antarctica?",
    "My Aadhaar is 1234 5678 9012 and PAN ABCDE1234F. What is the room rent limit?",
]

sample_cols = st.columns(len(sample_queries))
selected_sample = ""
for idx, q in enumerate(sample_queries):
    label = q.split("?")[0][:22] + "..."
    if sample_cols[idx].button(label, key=f"sq_{idx}"):
        selected_sample = q

user_query = st.text_input(
    "Enter insurance policy question:",
    value=selected_sample if selected_sample else "",
    placeholder="e.g. What is the cataract surgery waiting period?",
)

if st.button("Submit Query", type="primary") and user_query:
    with st.spinner("Analyzing policy clauses, schedules, and visual tables..."):
        resp: GroundedQueryResponse = pipeline.query(user_query, doc_id=selected_doc_id)

    # 1. DPDP PII Alert
    if resp.pii_redactions_applied:
        st.warning(
            f"🛡️ **DPDP Act 2023 Redaction Applied:** Masked {', '.join(resp.pii_redactions_applied)} identifiers."
        )

    # 2. Intent & Escalation
    intent_col1, intent_col2, intent_col3 = st.columns(3)
    intent_col1.info(f"**Intent:** `{resp.intent.primary_section}`")
    intent_col2.info(f"**CRAG Hops:** {resp.crag_hops} Hop(s)")
    intent_col3.info(f"**Model Tier:** `{resp.model_used}`")

    # 3. Legal Precedence Banner
    st.info(f"⚖️ **IRDAI Legal Precedence:** {resp.precedence_check.rule_applied}")

    # 4. Answer Card & Confidence
    st.markdown("### Grounded Policy Determination")
    conf_col, status_col = st.columns([1, 3])
    if resp.abstained or resp.confidence_score < 0.70:
        conf_col.error(f"Confidence: {resp.confidence_score * 100:.1f}% (Abstained)")
        st.error(
            f"⚠️ **IRDAI Indeterminate Abstention:** {resp.abstention_reason or 'Confidence below 0.70 threshold.'}"
        )
    else:
        conf_col.success(f"Confidence: {resp.confidence_score * 100:.1f}% (Verified)")

    st.write(resp.answer)

    # 5. Policy Coverage Breakdown
    st.markdown("#### Structured Policy Coverage Matrix")
    cov_data = {
        "Coverage Dimension": [
            "Coverage Status",
            "Waiting Period Details",
            "Applicable Sub-Limits",
            "Cost Sharing / Co-Pay",
            "Applicable Exclusions",
        ],
        "Policy Determination": [
            resp.coverage_summary.coverage_status,
            resp.coverage_summary.waiting_period_details,
            resp.coverage_summary.applicable_sub_limits,
            resp.coverage_summary.cost_sharing_or_deductible,
            ", ".join(resp.coverage_summary.applicable_exclusions) or "None",
        ],
    }
    st.table(cov_data)

    # 6. Citations & Visual Table Grounding
    st.markdown("#### Grounded Citations & Visual Inspector")
    if resp.citations:
        for idx, cit in enumerate(resp.citations):
            with st.expander(
                f"Citation {idx + 1}: [{cit.clause_code or f'Page {cit.page_number}'}] {cit.section_title}"
            ):
                cit_col1, cit_col2 = st.columns([2, 1])
                with cit_col1:
                    st.markdown(f'**Verbatim Quote:**\n> *"{cit.verbatim_quote}"*')
                    st.markdown(
                        f"**Parent Section Context:**\n```\n{cit.parent_context_preview}\n```"
                    )
                    st.caption(
                        f"Doc: `{cit.doc_id}` | Parent: `{cit.parent_id}` | Relevance: `{cit.relevance_score:.4f}`"
                    )
                with cit_col2:
                    if cit.image_crop_url:
                        crop_name = Path(cit.image_crop_url).name
                        crop_path = get_settings().crops_dir / crop_name
                        if crop_path.exists():
                            st.image(
                                str(crop_path),
                                caption=f"200-DPI Visual Table (Page {cit.page_number})",
                            )
    else:
        st.info("No citations available for this response.")

    # 7. OpenTelemetry Execution Waterfall
    st.markdown("#### OpenTelemetry Execution Waterfall")
    waterfall_rows: list[dict[str, Any]] = [
        {
            "Span Name": s.name,
            "Start Offset (ms)": s.start_offset_ms,
            "Duration (ms)": s.duration_ms,
            "Status": s.status,
        }
        for s in resp.trace_spans
    ]
    st.dataframe(waterfall_rows, use_container_width=True)
