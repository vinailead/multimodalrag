"""Unit tests for Phase 1: Provider Policy Catalog & Indicative Actuarial Premium Engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from insurance_mmrag.domain.policy_catalog import (
    POLICY_CATALOG,
    get_policy_card,
    list_health_policy_cards,
    list_policy_cards,
)
from insurance_mmrag.domain.premium_calculator import PremiumCalculator
from insurance_mmrag.schemas import ApplicantProfile


def test_all_manifest_policies_in_catalog() -> None:
    manifest_path = Path("data/raw_policies/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest) == 6

    for item in manifest:
        doc_id = str(item["doc_id"])
        card = get_policy_card(doc_id)
        assert card.doc_id == doc_id
        assert card.uin == item["uin"]
        assert len(card.sum_insured_options_inr) >= 5
        assert len(card.key_strengths) >= 2
        assert len(card.fine_print_warnings) >= 1
        assert "room_rent" in card.feature_citations
        assert "ped_waiting" in card.feature_citations
        assert "copay" in card.feature_citations

    all_cards = list_policy_cards(include_accident=True)
    health_only = list_policy_cards(include_accident=False)
    assert len(all_cards) == 6
    assert len(health_only) == 5

    with pytest.raises(KeyError):
        get_policy_card("non_existent_policy_id")


def test_premium_calculator_non_smoker_discount_and_gst() -> None:
    calc = PremiumCalculator()
    profile_healthy = ApplicantProfile(
        proposer_age=26,
        family_size=5,
        is_smoker=False,
        is_drinker=False,
        includes_parents=False,
        eldest_member_age=28,
        city_tier="tier_1",
        target_sum_insured_inr=1_000_000,
    )
    prem = calc.calculate_premium("hdfc_ergo_optima_secure", profile_healthy)
    assert prem.doc_id == "hdfc_ergo_optima_secure"
    assert prem.effective_day_1_cover_inr == 2_000_000  # 2X Secure Benefit
    assert prem.healthy_lifestyle_discount_inr > 0
    assert prem.smoker_loading_inr == 0
    assert prem.total_annual_premium_inr == prem.net_premium_before_gst_inr + prem.gst_18_pct_inr
    assert prem.monthly_emi_inr == round(prem.total_annual_premium_inr / 12)
    assert any("Healthy Lifestyle Discount" in n for n in prem.pricing_notes)

    profile_smoker = profile_healthy.model_copy(update={"is_smoker": True})
    prem_smoker = calc.calculate_premium("hdfc_ergo_optima_secure", profile_smoker)
    assert prem_smoker.healthy_lifestyle_discount_inr == 0
    assert prem_smoker.smoker_loading_inr > 0
    assert prem_smoker.total_annual_premium_inr > prem.total_annual_premium_inr


def test_portfolio_split_for_26yo_family_of_5_with_parents() -> None:
    calc = PremiumCalculator()
    profile = ApplicantProfile(
        proposer_age=26,
        family_size=5,
        is_smoker=False,
        is_drinker=False,
        includes_parents=True,
        eldest_member_age=58,
        city_tier="tier_1",
        target_sum_insured_inr=1_000_000,
    )
    split = calc.evaluate_portfolio_split(profile)
    assert split.recommended_strategy == "SPLIT_PORTFOLIO"
    assert split.annual_savings_inr > 0
    assert split.split_total_annual_inr < split.single_floater_annual_inr
    assert split.combined_effective_cover_inr >= 3_000_000
    assert len(split.key_reasons_to_split) >= 3

    # Nuclear family without parents recommends SINGLE_FLOATER
    nuclear_profile = profile.model_copy(
        update={"includes_parents": False, "eldest_member_age": 26}
    )
    nuclear_split = calc.evaluate_portfolio_split(nuclear_profile)
    assert nuclear_split.recommended_strategy == "SINGLE_FLOATER"
    assert nuclear_split.annual_savings_inr == 0
    assert len(POLICY_CATALOG) == 6
    assert len(list_health_policy_cards()) == 5


def test_streamlit_app_headless_execution() -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(Path("ui/streamlit_app.py").resolve(), default_timeout=60)
    at.run()
    assert not at.exception

    # Click the first sample query button (26yo family of 5 advisor query) and verify execution
    at.button[0].click().run()
    assert not at.exception
