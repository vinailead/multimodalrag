"""Google Material Design 3 Consumer Product Streamlit App for Indian Insurance Multimodal RAG."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from insurance_mmrag.config import get_settings
from insurance_mmrag.domain.policy_catalog import list_health_policy_cards, list_policy_cards
from insurance_mmrag.ingestion.sample_policy_factory import (
    create_arogya_sanjeevani_pdf,
    create_saral_suraksha_bima_pdf,
)
from insurance_mmrag.pipeline import InsuranceMMRAGPipeline, create_default_pipeline
from insurance_mmrag.schemas import (
    AdvisorRecommendationResponse,
    ApplicantProfile,
    GroundedQueryResponse,
)

st.set_page_config(
    page_title="Indian Insurance Policy Advisor & Multimodal RAG",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_cached_pipeline(
    api_key: str | None = None, use_stub: bool = True
) -> InsuranceMMRAGPipeline:
    import contextlib
    import json

    settings = get_settings()
    pipe = create_default_pipeline(settings=settings, use_stub=use_stub, api_key=api_key)

    manifest_file = settings.raw_policies_dir / "manifest.json"
    if manifest_file.exists():
        with contextlib.suppress(Exception):
            entries = json.loads(manifest_file.read_text(encoding="utf-8"))
            for entry in entries:
                file_path = Path(entry.get("file_path", ""))
                if not file_path.is_absolute():
                    file_path = Path.cwd() / file_path
                if file_path.exists():
                    pipe.ingest_pdf(file_path, doc_id=entry.get("doc_id"))

    if not pipe.get_indexed_documents():
        p1 = settings.raw_policies_dir / "arogya_sanjeevani_policy_wordings.pdf"
        if not p1.exists():
            create_arogya_sanjeevani_pdf(p1)
        pipe.ingest_pdf(p1, doc_id="arogya_sanjeevani_national")

        p2 = settings.raw_policies_dir / "saral_suraksha_bima.pdf"
        if not p2.exists():
            create_saral_suraksha_bima_pdf(p2)
        pipe.ingest_pdf(p2, doc_id="saral_suraksha_hdfc_ergo")

    return pipe


def render_advisor_section(rec: AdvisorRecommendationResponse) -> None:
    """Render the Needs-Discovery Probing Advisor, Portfolio Split, and Ranked Policy Cards."""
    with st.container(border=True):
        st.subheader("🎯 Personalized Underwriting & Advisory Verdict")
        st.markdown(f"**{rec.executive_advisory_summary}**")
        p = rec.extracted_profile
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Proposer Age", f"{p.proposer_age} yrs")
        c2.metric("Family Size", f"{p.family_size} members")
        c3.metric(
            "Non-Smoker / Non-Drinker",
            "Yes (-7.5%)" if not p.is_smoker and not p.is_drinker else "Standard",
        )
        c4.metric("Target Sum Insured", f"₹{p.target_sum_insured_inr:,}")
        c5.metric("Profile Completeness", f"{rec.completeness_pct}%")

    split = rec.portfolio_split_advice
    st.success(
        f"**{split.headline}**\n\n{split.explanation}",
        icon="💡",
    )
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Single Floater (All Together)", f"₹{split.single_floater_annual_inr:,}/yr")
    sc2.metric("Split 1: Young Nuclear Floater", f"₹{split.split_young_floater_annual_inr:,}/yr")
    sc3.metric("Split 2: Parents Floater", f"₹{split.split_parents_floater_annual_inr:,}/yr")
    sc4.metric(
        "Combined Split Total",
        f"₹{split.split_total_annual_inr:,}/yr",
        delta=f"-₹{split.annual_savings_inr:,}/yr saved",
        delta_color="inverse",
    )

    st.markdown("### 🏆 Top Recommended Policies (With Indicative GST-Inclusive Premiums)")
    for item in rec.ranked_policies:
        with st.container(border=True):
            top_left, top_right = st.columns([3, 2])
            with top_left:
                st.markdown(
                    f"#### #{item.rank} {item.feature_card.policy_name} — `{item.badge}`"
                )
                st.caption(
                    f"Insurer: **{item.feature_card.insurer_name}** | UIN: `{item.feature_card.uin}` | Category: `{item.feature_card.policy_category}`"
                )
            with top_right:
                st.metric(
                    f"Match Score: {item.match_score:.1f}%",
                    f"₹{item.premium.total_annual_premium_inr:,} / year",
                    f"₹{item.premium.monthly_emi_inr:,}/mo (incl. 18% GST)",
                )

            m1, m2, m3, m4 = st.columns(4)
            m1.markdown(f"**Room Rent Limit:**\n{item.feature_card.room_rent_limit}")
            m2.markdown(
                f"**PED Waiting (`Excl01`):**\n{item.feature_card.ped_waiting_months} Months"
            )
            m3.markdown(f"**Mandatory Co-Pay:**\n{item.feature_card.mandatory_copay_pct:.0f}%")
            m4.markdown(
                f"**Healthy Discount:**\n-₹{item.premium.healthy_lifestyle_discount_inr:,}/yr"
            )

            col_fit, col_warn = st.columns(2)
            with col_fit:
                st.markdown("**Why this fits your profile:**")
                for w in item.why_recommended_for_you:
                    st.markdown(f"- ✅ {w}")
            with col_warn:
                st.markdown("**Clause-Grounded Trade-Offs & Watch-Outs:**")
                for t in item.watch_out_for:
                    st.markdown(f"- ⚠️ {t}")


# --- Sidebar: Policy Selector, Model Config & Telemetry ---
st.sidebar.title("🛡️ IRDAI Insurance Advisor")
st.sidebar.caption("Clause-Grounded Q&A · Probing Underwriter · Policy Comparator")

with st.sidebar.expander("⚙️ Model Engine Configuration", expanded=False):
    live_key = st.text_input(
        "Gemini API Key (Optional):",
        type="password",
        help="Leave blank to use the deterministic engine with zero external API calls.",
    )

use_live_model = bool(live_key.strip()) if live_key else False
pipeline = get_cached_pipeline(
    api_key=live_key if use_live_model else None, use_stub=not use_live_model
)

docs = pipeline.get_indexed_documents()
policy_options = {doc.doc_id: f"{doc.policy_name} ({doc.uin})" for doc in docs.values()}
selected_doc_id = st.sidebar.selectbox(
    "Active Policy (for Specific Policy Q&A)",
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

# --- Main Workspace Header & 3-Pillar Product Tabs ---
st.title("Indian Insurance Policy Advisor, Comparator & Multimodal RAG")
st.markdown(
    "Get **instant, plain-English answers** for a specific policy, discover the **best policy for your family profile** "
    "with indicative annual/monthly ₹ premiums, or **compare all listed providers side-by-side** with an Out-of-Pocket Hospital Bill Simulator."
)

tab_qa, tab_advisor, tab_compare = st.tabs(
    [
        "🔍 1. Ask Specific Policy Q&A",
        "🧭 2. Find Best Policy for Me (AI Advisor)",
        "⚖️ 3. Compare Policies & Claim Simulator",
    ]
)

# ============================================================================
# TAB 1: SPECIFIC POLICY Q&A (Plus Auto-Routed Advisor)
# ============================================================================
with tab_qa:
    if "active_query" not in st.session_state:
        st.session_state["active_query"] = "is cataract surgery included or excluded"
    if "auto_execute" not in st.session_state:
        st.session_state["auto_execute"] = False

    st.markdown("##### 💡 Quick Sample Inquiries (Click any question to run immediately):")
    sample_queries = [
        "I am individual with age 26, non smoker and non drinker with family of 5 what is the best policy for me",
        "is cataract surgery included or excluded",
        "What is the waiting period for cataract surgery under this policy?",
        "What is the daily room rent sub-limit and mandatory co-payment percentage?",
        "What is the waiting period for Pre-Existing Diseases under Code-Excl01?",
        "My Aadhaar is 1234 5678 9012 and PAN ABCDE1234F. What is the room rent limit?",
    ]

    sample_cols = st.columns(2)
    for idx, q in enumerate(sample_queries):
        col_idx = idx % 2
        if sample_cols[col_idx].button(f"📌 {q}", key=f"sq_{idx}", width="stretch"):
            st.session_state["active_query"] = q
            st.session_state["auto_execute"] = True
            st.rerun()

    with st.form("insurance_query_form", clear_on_submit=False):
        col_input, col_submit = st.columns([5, 1])
        with col_input:
            user_query_input = st.text_input(
                "Enter policy inquiry or personal recommendation question:",
                value=st.session_state.get("active_query", ""),
                placeholder="e.g. is cataract surgery included or excluded",
                label_visibility="collapsed",
            )
        with col_submit:
            submit_clicked = st.form_submit_button("🔍 Ask", type="primary", width="stretch")

    should_run_query = (submit_clicked or st.session_state.get("auto_execute", False)) and bool(
        user_query_input.strip()
    )
    st.session_state["auto_execute"] = False

    if should_run_query:
        active_query_text = user_query_input.strip()
        with st.spinner("Analyzing policy clauses, exclusions, schedules, and underwriting rules..."):
            resp: GroundedQueryResponse = pipeline.query(
                active_query_text, doc_id=selected_doc_id
            )

        if resp.pii_redactions_applied:
            st.warning(
                f"🛡️ **DPDP Act 2023 Masking Applied:** Redacted sensitive Indian identifier(s): `{', '.join(resp.pii_redactions_applied)}`."
            )

        st.markdown("### 📋 Direct Answer & Policy Determination")
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
            st.success(f"**Coverage Status:** {badge_label}\n\n{resp.answer}")

        if resp.advisor_recommendation is not None:
            st.markdown("---")
            render_advisor_section(resp.advisor_recommendation)

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

        with st.expander(
            f"📑 Grounded Policy Citations & Visual Table Inspector ({len(resp.citations)} sources)",
            expanded=False,
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

# ============================================================================
# TAB 2: PERSONALIZED AI POLICY ADVISOR & PROBING WIZARD
# ============================================================================
with tab_advisor:
    st.subheader("🧭 Conversational Needs-Discovery & Policy Recommendation Engine")
    st.markdown(
        "Tell us about yourself in plain English **and/or refine the probing questions below**. "
        "Our fiduciary advisor diagnoses **Family Floater age-band traps**, applies **Non-Smoker/Non-Drinker discounts**, "
        "and ranks every policy with indicative annual and monthly ₹ premiums."
    )

    advisor_nl_query = st.text_input(
        "Your Requirement / Persona:",
        value="I am individual with age 26, non smoker and non drinker with family of 5 what is the best policy for me",
        key="advisor_nl_input",
    )

    with st.container(border=True):
        st.markdown("##### 🔎 Interactive Needs-Discovery Probing Questions (Refine Your Quote Live)")
        pc1, pc2 = st.columns(2)
        with pc1:
            probe_parents = st.selectbox(
                "1. Does your family include senior parents (aged 50+)?",
                options=[
                    "Yes — Parents aged 50-60 included in the 5 members",
                    "No — Spouse & Kids only (all under 35)",
                    "Yes — Senior Citizen Parents aged 60+",
                ],
                index=0,
            )
            probe_ped = st.selectbox(
                "2. Does any member have Pre-Existing Diseases (Diabetes, BP, Thyroid, Asthma)?",
                options=[
                    "No pre-existing conditions (everyone is healthy)",
                    "Yes — Diabetes / Hypertension / Thyroid",
                    "Need Maternity Cover within 2 years",
                ],
                index=0,
            )
        with pc2:
            probe_city = st.selectbox(
                "3. Which City Tier do you live in (determines hospital room rent)?",
                options=[
                    "Tier-1 Metro (Mumbai, Delhi, Bengaluru, Chennai, Hyderabad, Pune)",
                    "Tier-2 City (Coimbatore, Jaipur, Indore, Kochi, Lucknow)",
                    "Tier-3 Town",
                ],
                index=0,
            )
            probe_priority = st.selectbox(
                "4. What is your #1 priority when choosing a policy?",
                options=[
                    "Balanced Coverage & Value (₹10L-₹15L cover)",
                    "Maximum Hospital Coverage & Zero Out-of-Pocket",
                    "Lowest Annual Premium (Budget Cap under ₹18,000/yr)",
                ],
                index=0,
            )

        target_si = st.select_slider(
            "Target Base Sum Insured (₹):",
            options=[500_000, 1_000_000, 1_500_000, 2_500_000],
            value=1_000_000,
            format_func=lambda v: f"₹{v // 100_000} Lakhs (₹{v:,})",
        )

    combined_advisor_query = (
        f"{advisor_nl_query}. {probe_parents}. {probe_ped}. {probe_city}. {probe_priority}."
    )
    advisor_res = pipeline.recommend_policies(user_query=combined_advisor_query)
    if target_si != advisor_res.extracted_profile.target_sum_insured_inr:
        updated_prof = advisor_res.extracted_profile.model_copy(
            update={"target_sum_insured_inr": target_si}
        )
        advisor_res = pipeline.recommend_policies(
            user_query=combined_advisor_query,
            profile=updated_prof,
        )

    render_advisor_section(advisor_res)

# ============================================================================
# TAB 3: MULTI-POLICY SIDE-BY-SIDE COMPARATOR & CLAIM BILL SIMULATOR
# ============================================================================
with tab_compare:
    st.subheader("⚖️ Multi-Policy Side-by-Side Comparison & Out-of-Pocket Claim Simulator")
    all_cards = list_policy_cards()
    health_ids = [c.doc_id for c in list_health_policy_cards()]
    card_labels = {c.doc_id: f"{c.policy_name} ({c.insurer_name})" for c in all_cards}

    selected_compare_ids = st.multiselect(
        "Select Policies to Compare Side-by-Side:",
        options=[c.doc_id for c in all_cards],
        default=health_ids,
        format_func=lambda d: card_labels.get(d, d),
    )

    comp_col1, comp_col2, comp_col3 = st.columns(3)
    comp_age = comp_col1.number_input("Proposer Age (yrs)", min_value=18, max_value=75, value=26)
    comp_family = comp_col2.number_input("Family Size", min_value=1, max_value=8, value=5)
    comp_si = comp_col3.selectbox(
        "Sum Insured (₹)",
        options=[500_000, 1_000_000, 1_500_000, 2_500_000],
        index=1,
        format_func=lambda v: f"₹{v // 100_000} Lakhs",
    )

    comp_profile = ApplicantProfile(
        proposer_age=int(comp_age),
        family_size=int(comp_family),
        is_smoker=False,
        is_drinker=False,
        target_sum_insured_inr=int(comp_si),
    )

    comparison = pipeline.compare_policies(
        doc_ids=selected_compare_ids or health_ids,
        profile=comp_profile,
    )

    st.info(f"**Executive Comparison Verdict:** {comparison.fiduciary_summary}")

    matrix_rows: list[dict[str, Any]] = []
    for row in comparison.comparison_rows:
        entry: dict[str, Any] = {
            "Feature / IRDAI Parameter": row.parameter_label,
            "Why It Matters": row.consumer_tooltip,
        }
        for p_card in comparison.compared_policies:
            cell = row.cells.get(p_card.doc_id)
            if cell is not None:
                star = " ★" if cell.is_winner else ""
                cit = f" [Pg {cell.citation.page_number}]" if cell.citation else ""
                entry[p_card.policy_name] = f"{cell.display_value}{star}{cit}"
        matrix_rows.append(entry)

    st.dataframe(matrix_rows, width="stretch", hide_index=True)

    st.markdown("---")
    st.subheader("🏥 Interactive Hospital Bill Out-of-Pocket Claim Simulator")
    st.markdown(
        "See how **Room Rent proportionate deductions**, **Cataract sub-limits**, **Non-medical consumables (~8% of bill)**, "
        "and **Mandatory Co-payment** affect what the insurer actually pays vs. what you pay out-of-pocket."
    )

    sim_c1, sim_c2, sim_c3, sim_c4 = st.columns(4)
    sim_bill = sim_c1.number_input(
        "Total Hospital Bill (₹)", min_value=20_000, max_value=2_000_000, value=250_000, step=25_000
    )
    sim_room = sim_c2.number_input(
        "Hospital Room Rent / Day (₹)", min_value=2_000, max_value=30_000, value=9_000, step=1_000
    )
    sim_days = sim_c3.number_input("Stay Duration (Days)", min_value=1, max_value=30, value=4)
    sim_cataract = sim_c4.checkbox("Is this Cataract Surgery?", value=False)

    sim_result = pipeline.simulate_claim(
        doc_ids=selected_compare_ids or health_ids,
        claimed_bill_inr=int(sim_bill),
        hospital_room_rent_per_day_inr=int(sim_room),
        days_hospitalized=int(sim_days),
        procedure_type="cataract_surgery" if sim_cataract else "general_hospitalization",
        sum_insured_inr=int(comp_si),
    )

    sim_table: list[dict[str, Any]] = [
        {
            "Policy": item.policy_name,
            "Total Bill (₹)": f"₹{item.claimed_bill_inr:,}",
            "Insurer Pays (₹)": f"₹{item.insurer_payable_inr:,}",
            "You Pay Out-of-Pocket (₹)": f"₹{item.user_out_of_pocket_inr:,}",
            "Room Rent Penalty": f"₹{item.room_rent_deduction_inr:,}",
            "Consumables Deduction": f"₹{item.consumables_deduction_inr:,}",
            "Co-Pay / Sub-Limit": f"₹{item.copay_deduction_inr + item.procedure_sublimit_deduction_inr:,}",
            "Actuarial Breakdown": item.explanation,
        }
        for item in sim_result.results
    ]
    st.dataframe(sim_table, width="stretch", hide_index=True)
