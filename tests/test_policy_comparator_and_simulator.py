"""Unit tests for Phase 3: Multi-Policy Comparator & Out-of-Pocket Claim Bill Simulator."""

from __future__ import annotations

from insurance_mmrag.advisor.claim_simulator import ClaimSimulator
from insurance_mmrag.advisor.policy_comparator import PolicyComparator
from insurance_mmrag.schemas import ApplicantProfile


def test_multi_policy_comparison_matrix_citations() -> None:
    comparator = PolicyComparator()
    profile = ApplicantProfile(
        proposer_age=26,
        family_size=5,
        is_smoker=False,
        is_drinker=False,
        city_tier="tier_1",
        target_sum_insured_inr=1_000_000,
    )
    doc_ids = [
        "hdfc_ergo_optima_secure",
        "tata_aig_medicare_premier",
        "bajaj_allianz_health_guard",
        "godigit_health_plus",
        "arogya_sanjeevani_national",
    ]
    comp = comparator.compare(doc_ids=doc_ids, profile=profile)

    assert len(comp.compared_policies) == 5
    assert len(comp.comparison_rows) == 10
    assert set(comp.premiums.keys()) == set(doc_ids)

    for row in comp.comparison_rows:
        assert len(row.cells) == 5
        for did in doc_ids:
            cell = row.cells[did]
            assert cell.display_value != ""
            assert cell.citation is not None
            assert cell.citation.doc_id == did
            assert cell.citation.page_number >= 1
            assert len(cell.citation.verbatim_quote) >= 15


def test_claim_simulator_room_rent_and_cataract_sublimits() -> None:
    sim = ClaimSimulator()

    # Scenario 1: General hospitalization ₹1,20,000 in ₹8,000/day room
    res_general = sim.simulate(
        claimed_bill_inr=120_000,
        hospital_room_rent_per_day_inr=8_000,
        days_hospitalized=3,
        procedure_type="general_hospitalization",
        sum_insured_inr=1_000_000,
        doc_ids=[
            "hdfc_ergo_optima_secure",
            "arogya_sanjeevani_national",
            "saral_suraksha_hdfc_ergo",
        ],
    )
    by_id = {item.doc_id: item for item in res_general.results}

    # HDFC ERGO Optima Secure: 0 room cap, 0 copay, consumables covered -> 100% paid
    optima = by_id["hdfc_ergo_optima_secure"]
    assert optima.user_out_of_pocket_inr == 0
    assert optima.insurer_payable_inr == 120_000
    assert optima.coverage_ratio_pct == 100.0

    # Arogya Sanjeevani: ₹5,000/day room cap + proportionate deduction + 8% consumables + 5% copay
    arogya = by_id["arogya_sanjeevani_national"]
    assert arogya.room_rent_deduction_inr > 0
    assert arogya.consumables_deduction_inr > 0
    assert arogya.copay_deduction_inr > 0
    assert arogya.user_out_of_pocket_inr > 35_000
    assert arogya.insurer_payable_inr < 85_000

    # Saral Suraksha: Personal Accident does not cover general illness hospitalization
    saral = by_id["saral_suraksha_hdfc_ergo"]
    assert saral.insurer_payable_inr == 0
    assert saral.user_out_of_pocket_inr == 120_000

    # Scenario 2: Cataract surgery ₹75,000 per eye
    res_cataract = sim.simulate(
        claimed_bill_inr=75_000,
        hospital_room_rent_per_day_inr=4_500,
        days_hospitalized=1,
        procedure_type="cataract_surgery",
        sum_insured_inr=500_000,
        doc_ids=["hdfc_ergo_optima_secure", "arogya_sanjeevani_national"],
    )
    cat_by_id = {item.doc_id: item for item in res_cataract.results}
    assert cat_by_id["hdfc_ergo_optima_secure"].procedure_sublimit_deduction_inr == 0
    assert cat_by_id["arogya_sanjeevani_national"].procedure_sublimit_deduction_inr > 0
    assert cat_by_id["arogya_sanjeevani_national"].insurer_payable_inr <= 40_000
