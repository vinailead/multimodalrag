"""Google Material Design 3 Interactive Streamlit Dashboard for Indian Insurance Multimodal RAG."""

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
def get_cached_pipeline(
    api_key: str | None = None, use_stub: bool = True
) -> InsuranceMMRAGPipeline:
    import json

    settings = get_settings()
    pipe = create_default_pipeline(settings=settings, use_stub=use_stub, api_key=api_key)

    # Ingest all available provider policies from manifest.json
    manifest_file = settings.raw_policies_dir / "manifest.json"
    if manifest_file.exists():
        try:
            entries = json.loads(manifest_file.read_text(encoding="utf-8"))
            for entry in entries:
                file_path = Path(entry.get("file_path", ""))
                if not file_path.is_absolute():
                    file_path = Path.cwd() / file_path
                if file_path.exists():
                    pipe.ingest_pdf(file_path, doc_id=entry.get("doc_id"))
        except Exception:
            pass

    # Ensure baseline policies exist if manifest was not loaded
    if not pipe.get_indexed_documents():
        p1 = settings.raw_policies_dir / "arogya_sanjeevani_policy_wordings.pdf"
        if not p1.exists():
            create_arogya_sanjeevani_pdf(p1)
        pipe.ingest_pdf(p1, doc_id="arogya_sanjeevani_national")

        p2 = settings.raw_policies_dir / "saral_suraksha_bima.pdf"
        if not p2.exists():
            create_saral_suraksha_bima_pdf(p2)
        pipe.ingest_pdf(p2, doc_id="saral_suraksha_bima_hdfc")

    return pipe


# --- Sidebar: Policy Selector, Model Config & Telemetry ---
st.sidebar.title("🛡️ IRDAI Multimodal RAG")
st.sidebar.caption("Gemini 2.5 Vision · Structure-Aware · DPDP Compliant")

# Model Mode Selector
with st.sidebar.expander("⚙️ Model Engine Configuration", expanded=False):
    live_key = st.text_input(
        "Gemini API Key (Optional):",
        type="password",
        help="Leave blank to use the high-speed deterministic engine with zero external API calls.",
    )

use_live_model = bool(live_key.strip()) if live_key else False
pipeline = get_cached_pipeline(api_key=live_key if use_live_model else None, use_stub=not use_live_model)

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
if use_live_model:
    st.sidebar.info("🟢 Live Gemini 2.5 Active")
else:
    st.sidebar.info("🔒 Deterministic In-Memory Double Active")

# --- Main Workspace ---
st.title("Indian Insurance Policy Multimodal RAG")
st.markdown(
    "Ask any question about exclusions, waiting periods (`Excl01` to `Excl18`), sub-limits, or benefit schedules. "
    "Powered by **Gemini 2.5 Vision table extraction**, **Parent-Child chunking**, and **OpenTelemetry waterfall execution tracing**."
)

# State initialization for seamless one-click queries
if "active_query" not in st.session_state:
    st.session_state["active_query"] = "is cataract surgery included or excluded"
if "auto_execute" not in st.session_state:
    st.session_state["auto_execute"] = False

# Quick Sample Inquiries
st.markdown("##### 💡 Quick Sample Inquiries (Click to Ask):")
sample_queries = [
    "is cataract surgery included or excluded",
    "What is the waiting period for cataract surgery under this policy?",
    "What is the daily room rent sub-limit and mandatory co-payment percentage?",
    "What is the waiting period for Pre-Existing Diseases under Code-Excl01?",
    "Does this insurance policy cover pet veterinary dental implants in Antarctica?",
    "My Aadhaar is 1234 5678 9012 and PAN ABCDE1234F. What is the room rent limit?",
]

sample_cols = st.columns(3)
for idx, q in enumerate(sample_queries):
    col_idx = idx % 3
    if sample_cols[col_idx].button(f"📌 {q}", key=f"sq_{idx}", use_container_width=True):
        st.session_state["active_query"] = q
        st.session_state["auto_execute"] = True
        st.rerun()

# Form handles pressing Enter in the text input box
with st.form("insurance_query_form", clear_on_submit=False):
    col_input, col_submit = st.columns([5, 1])
    with col_input:
        user_query_input = st.text_input(
            "Enter policy inquiry (Press Enter or click Ask Assistant):",
            value=st.session_state.get("active_query", ""),
            placeholder="e.g. is cataract surgery included or excluded",
            label_visibility="collapsed",
        )
    with col_submit:
        submit_clicked = st.form_submit_button(
            "🔍 Ask", type="primary", use_container_width=True
        )

# Execute query if submitted via button, Enter key, or quick sample click
should_run_query = (submit_clicked or st.session_state.get("auto_execute", False)) and bool(
    user_query_input.strip()
)
st.session_state["auto_execute"] = False

if should_run_query:
    active_query_text = user_query_input.strip()
    with st.spinner("Analyzing policy clauses, exclusions, schedules, and visual tables..."):
        resp: GroundedQueryResponse = pipeline.query(active_query_text, doc_id=selected_doc_id)

    # 1. DPDP PII Alert
    if resp.pii_redactions_applied:
        st.warning(
            f"🛡️ **DPDP Act 2023 Masking Applied:** Redacted sensitive Indian identifier(s): `{', '.join(resp.pii_redactions_applied)}`."
        )

    # 2. Meta summary pills
    meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
    meta_col1.info(f"**Section:** `{resp.intent.primary_section}`")
    meta_col2.info(f"**Confidence:** `{resp.confidence_score * 100:.1f}%`")
    meta_col3.info(f"**CRAG Hops:** `{resp.crag_hops} Hop(s)`")
    meta_col4.info(f"**Model Tier:** `{resp.model_used}`")

    # 3. Direct Answer Card
    st.markdown("---")
    st.markdown("### 📋 Policy Determination & Direct Answer")

    status = resp.coverage_summary.coverage_status
    status_badges = {
        "COVERED": "🟢 FULLY COVERED",
        "COVERED_WITH_LIMITS": "🟡 COVERED WITH LIMITS / SUB-LIMITS",
        "WAITING_PERIOD_APPLIES": "⏳ WAITING PERIOD APPLIES",
        "EXCLUDED": "🔴 PERMANENTLY EXCLUDED",
        "INDETERMINATE": "⚪ INDETERMINATE COVERAGE",
    }
    badge_label = status_badges.get(status, status)

    if resp.abstained or resp.confidence_score < 0.70:
        st.warning(
            f"⚠️ **IRDAI Indeterminate Abstention (Confidence {resp.confidence_score * 100:.1f}%):**\n\n"
            f"{resp.abstention_reason or 'The query cannot be verified with >= 70% confidence against the policy clauses.'}"
        )
        st.markdown(f"> {resp.answer}")
    else:
        # High-visibility Direct Answer Banner
        st.success(f"**Coverage Status:** {badge_label}\n\n{resp.answer}")

    # 4. Policy Coverage Breakdown Table
    st.markdown("#### 📊 Key Coverage Breakdown")
    cov_data = {
        "Coverage Dimension": [
            "Coverage Determination",
            "Waiting Period Details",
            "Applicable Sub-Limits",
            "Cost Sharing / Co-Pay",
            "Applicable Exclusions",
        ],
        "Policy Terms & Conditions": [
            resp.coverage_summary.coverage_status,
            resp.coverage_summary.waiting_period_details,
            resp.coverage_summary.applicable_sub_limits,
            resp.coverage_summary.cost_sharing_or_deductible,
            ", ".join(resp.coverage_summary.applicable_exclusions) or "None",
        ],
    }
    st.table(cov_data)

    # 5. Citations & Visual Table Grounding
    with st.expander(
        f"📑 Grounded Policy Citations & Visual Table Inspector ({len(resp.citations)} sources)",
        expanded=True,
    ):
        if resp.citations:
            for idx, cit in enumerate(resp.citations):
                st.markdown(
                    f"**Citation {idx + 1}: [{cit.clause_code or f'Page {cit.page_number}'}] {cit.section_title}**"
                )
                cit_col1, cit_col2 = st.columns([2, 1])
                with cit_col1:
                    st.markdown(f'**Verbatim Policy Quote:**\n> *"{cit.verbatim_quote}"*')
                    st.caption(
                        f"Page {cit.page_number} | Doc ID: `{cit.doc_id}` | Parent Chunk: `{cit.parent_id}` | Relevance Score: `{cit.relevance_score:.4f}`"
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
                st.markdown("---")
        else:
            st.info("No policy citations were retrieved for this query.")

    # 6. OpenTelemetry Execution Waterfall
    with st.expander("⏱️ OpenTelemetry Execution Waterfall", expanded=False):
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
