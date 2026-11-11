"""Unit tests for Phase 2: Conversational Needs-Discovery & Probing Recommendation Engine."""

from __future__ import annotations

from pathlib import Path

from insurance_mmrag.advisor.recommendation_engine import (
    RecommendationEngine,
    is_advisory_or_comparison_query,
)
from insurance_mmrag.pipeline import create_default_pipeline
from insurance_mmrag.schemas import ApplicantProfile


def test_advisory_query_detection() -> None:
    assert is_advisory_or_comparison_query(
        "I am individual with age 26, non smoker and non drinker with family of 5 what is the best policy for me"
    )
    assert is_advisory_or_comparison_query("Compare policies across providers for my family")
    assert not is_advisory_or_comparison_query("What is the waiting period for cataract surgery?")


def test_26yo_family_of_5_probing_and_ranking() -> None:
    engine = RecommendationEngine()
    query = (
        "I am individual with age 26, non smoker and non drinker with family of 5 "
        "what is the best policy for me"
    )
    resp = engine.recommend(query)

    # Verify extracted profile slots
    assert resp.extracted_profile.proposer_age == 26
    assert resp.extracted_profile.family_size == 5
    assert resp.extracted_profile.is_smoker is False
    assert resp.extracted_profile.is_drinker is False

    # Verify probing questions are generated for missing slots
    assert resp.needs_probing is True
    assert len(resp.probing_questions) == 4
    slot_names = {q.slot_name for q in resp.probing_questions}
    assert "family_composition" in slot_names
    assert "pre_existing_diseases" in slot_names
    assert "city_tier" in slot_names
    assert "budget_priority" in slot_names

    # Verify portfolio split advice models the family-of-5 split
    assert resp.portfolio_split_advice.recommended_strategy == "SPLIT_PORTFOLIO"
    assert resp.portfolio_split_advice.annual_savings_inr > 0

    # Verify ranked policies and indicative premiums
    assert len(resp.ranked_policies) == 5
    top1 = resp.ranked_policies[0]
    assert top1.rank == 1
    assert top1.match_score >= 85.0
    assert top1.feature_card.doc_id in {"hdfc_ergo_optima_secure", "tata_aig_medicare_premier"}
    assert top1.premium.total_annual_premium_inr > 0
    assert top1.premium.healthy_lifestyle_discount_inr > 0


def test_complete_profile_needs_no_probing_and_adapts_ranking() -> None:
    engine = RecommendationEngine()
    # Complete profile with PEDs -> prioritizes shorter 24-month PED waiting period
    ped_profile = ApplicantProfile(
        proposer_age=26,
        family_size=5,
        is_smoker=False,
        is_drinker=False,
        includes_parents=True,
        eldest_member_age=56,
        has_pre_existing_diseases=True,
        pre_existing_conditions=["Diabetes", "Hypertension (BP)"],
        city_tier="tier_1",
        target_sum_insured_inr=1_500_000,
        budget_priority="comprehensive_zero_copay",
    )
    resp = engine.recommend(
        "Best policy for 26yo in Mumbai with parents aged 56 having diabetes, 15 lakhs comprehensive cover",
        explicit_profile=ped_profile,
    )
    assert resp.needs_probing is False
    assert len(resp.probing_questions) == 0
    assert resp.completeness_pct == 100
    assert resp.ranked_policies[0].feature_card.doc_id in {
        "hdfc_ergo_optima_secure",
        "tata_aig_medicare_premier",
    }

    # Budget priority -> Arogya Sanjeevani rises to top 2
    budget_profile = ped_profile.model_copy(
        update={
            "has_pre_existing_diseases": False,
            "city_tier": "tier_3",
            "budget_priority": "budget_low_premium",
        }
    )
    budget_resp = engine.recommend(
        "Cheapest budget policy in tier 3 town", explicit_profile=budget_profile
    )
    top_ids = [r.feature_card.doc_id for r in budget_resp.ranked_policies[:2]]
    assert "arogya_sanjeevani_national" in top_ids


def test_pipeline_query_enriches_advisory_response() -> None:
    pipeline = create_default_pipeline(use_stub=True)
    pipeline.ingest_pdf(
        Path("data/raw_policies/arogya_sanjeevani_policy_wordings.pdf"),
        doc_id="arogya_sanjeevani_national",
    )
    q = "I am individual with age 26, non smoker and non drinker with family of 5 what is the best policy for me"
    res = pipeline.query(q)
    assert res.abstained is False
    assert res.confidence_score >= 0.90
    assert res.advisor_recommendation is not None
    assert res.advisor_recommendation.extracted_profile.proposer_age == 26
    assert res.advisor_recommendation.extracted_profile.family_size == 5
    assert "Personalized Advisory" in res.answer
