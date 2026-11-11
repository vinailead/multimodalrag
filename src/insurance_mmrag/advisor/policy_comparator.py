"""Clause-Grounded Multi-Policy Side-by-Side Comparison Matrix Engine."""

from __future__ import annotations

from insurance_mmrag.advisor.claim_simulator import ClaimSimulator
from insurance_mmrag.domain.policy_catalog import get_policy_card, list_policy_cards
from insurance_mmrag.domain.premium_calculator import PremiumCalculator
from insurance_mmrag.schemas import (
    ApplicantProfile,
    ComparisonCell,
    ComparisonRow,
    PolicyComparisonResponse,
    PolicyFeatureCard,
    PremiumBreakdown,
)


class PolicyComparator:
    """Compares 2 to 6 Indian insurance policies across 10 IRDAI clause-grounded rows."""

    def __init__(self) -> None:
        self.premium_calc = PremiumCalculator()
        self.claim_sim = ClaimSimulator()

    def build_comparison_rows(
        self,
        cards: list[PolicyFeatureCard],
        premiums: dict[str, PremiumBreakdown],
    ) -> list[ComparisonRow]:
        rows: list[ComparisonRow] = []

        # Lowest health policy premium (excluding Personal Accident)
        health_prems = [
            premiums[c.doc_id].total_annual_premium_inr
            for c in cards
            if c.policy_category != "personal_accident"
        ]
        min_health_prem = min(health_prems) if health_prems else 0

        # 1. Annual & Monthly Premium
        prem_cells: dict[str, ComparisonCell] = {}
        for c in cards:
            p = premiums[c.doc_id]
            disc_tag = (
                f" (incl. -₹{p.healthy_lifestyle_discount_inr:,} non-smoker discount)"
                if p.healthy_lifestyle_discount_inr > 0
                else ""
            )
            is_win = (
                c.policy_category != "personal_accident"
                and p.total_annual_premium_inr == min_health_prem
            )
            prem_cells[c.doc_id] = ComparisonCell(
                doc_id=c.doc_id,
                display_value=f"₹{p.total_annual_premium_inr:,}/yr (₹{p.monthly_emi_inr:,}/mo){disc_tag}",
                sentiment="positive" if is_win else "neutral",
                is_winner=is_win,
                citation=c.feature_citations.get("effective_cover"),
            )
        rows.append(
            ComparisonRow(
                parameter_key="annual_premium",
                parameter_label="1. Indicative Annual & Monthly Premium (incl. 18% GST)",
                consumer_tooltip="Estimated annual & monthly outlay for your family size, eldest member age band, city tier, and non-smoker status.",
                cells=prem_cells,
            )
        )

        # 2. Effective Day-1 Sum Insured
        max_day1 = max((premiums[c.doc_id].effective_day_1_cover_inr for c in cards), default=0)
        cover_cells: dict[str, ComparisonCell] = {}
        for c in cards:
            p = premiums[c.doc_id]
            lakhs = p.effective_day_1_cover_inr / 100_000.0
            base_lakhs = p.sum_insured_inr / 100_000.0
            is_win = p.effective_day_1_cover_inr == max_day1 and c.day_1_cover_multiplier > 1.0
            cover_cells[c.doc_id] = ComparisonCell(
                doc_id=c.doc_id,
                display_value=(
                    f"₹{lakhs:.0f} Lakhs usable Day-1 (Base ₹{base_lakhs:.0f}L x {c.day_1_cover_multiplier:.0f}X) — {c.effective_cover_note}"
                ),
                sentiment="positive" if c.day_1_cover_multiplier > 1.0 else "neutral",
                is_winner=is_win,
                citation=c.feature_citations.get("effective_cover"),
            )
        rows.append(
            ComparisonRow(
                parameter_key="effective_cover",
                parameter_label="2. Effective Day-1 Sum Insured & Multiplier",
                consumer_tooltip="Actual hospital coverage available from Day 1 of the policy before restoration or renewal bonuses.",
                cells=cover_cells,
            )
        )

        # 3. Room Rent & ICU Sub-Limit
        room_cells: dict[str, ComparisonCell] = {}
        for c in cards:
            has_cap = c.has_room_rent_cap
            no_prop = not has_cap and not c.proportionate_deduction_applies
            room_cells[c.doc_id] = ComparisonCell(
                doc_id=c.doc_id,
                display_value=f"{c.room_rent_limit} | ICU: {c.icu_limit}",
                sentiment="negative" if has_cap else ("positive" if no_prop else "neutral"),
                is_winner=no_prop,
                citation=c.feature_citations.get("room_rent"),
            )
        rows.append(
            ComparisonRow(
                parameter_key="room_rent",
                parameter_label="3. Room Rent & ICU Sub-Limits (Proportionate Deduction Risk)",
                consumer_tooltip="CRITICAL: Policies with a 2% SI or ₹5,000/day room cap slash your surgeon, doctor, and OT payout proportionately if you pick a pricier room.",
                cells=room_cells,
            )
        )

        # 4. Pre-Existing Disease (PED) Waiting Period (Excl01)
        ped_cells: dict[str, ComparisonCell] = {}
        for c in cards:
            if c.policy_category == "personal_accident":
                ped_cells[c.doc_id] = ComparisonCell(
                    doc_id=c.doc_id,
                    display_value="Illness Excluded (Accident Cover Only)",
                    sentiment="warning",
                    is_winner=False,
                    citation=c.feature_citations.get("ped_waiting"),
                )
            else:
                is_short = c.ped_waiting_months <= 24
                ped_cells[c.doc_id] = ComparisonCell(
                    doc_id=c.doc_id,
                    display_value=f"{c.ped_waiting_months} Months ({c.ped_waiting_months // 12} Years) under Code-Excl01",
                    sentiment="positive"
                    if is_short
                    else ("warning" if c.ped_waiting_months >= 48 else "neutral"),
                    is_winner=is_short,
                    citation=c.feature_citations.get("ped_waiting"),
                )
        rows.append(
            ComparisonRow(
                parameter_key="ped_waiting",
                parameter_label="4. Pre-Existing Disease (PED) Waiting Period (Code-Excl01)",
                consumer_tooltip="Waiting period before declared conditions like Diabetes, Hypertension, or Thyroid are covered.",
                cells=ped_cells,
            )
        )

        # 5. Specific Disease Waiting Period (Excl02) & Cataract Sub-limit
        spec_cells: dict[str, ComparisonCell] = {}
        for c in cards:
            no_cat_cap = (
                c.cataract_max_per_eye_inr is None and c.policy_category != "personal_accident"
            )
            spec_cells[c.doc_id] = ComparisonCell(
                doc_id=c.doc_id,
                display_value=(
                    f"{c.specific_disease_waiting_months} Months wait (Code-Excl02) | Cataract: {c.cataract_limit_description}"
                ),
                sentiment="positive"
                if no_cat_cap
                else ("warning" if (c.cataract_max_per_eye_inr or 0) <= 40_000 else "neutral"),
                is_winner=no_cat_cap,
                citation=c.feature_citations.get("specific_waiting"),
            )
        rows.append(
            ComparisonRow(
                parameter_key="specific_waiting",
                parameter_label="5. Specific Surgeries Waiting (Code-Excl02) & Cataract Limit",
                consumer_tooltip="Waiting period and per-eye monetary cap for scheduled surgeries like Cataract, Hernia, Hysterectomy, and Joint Replacement.",
                cells=spec_cells,
            )
        )

        # 6. Mandatory Co-Payment
        copay_cells: dict[str, ComparisonCell] = {}
        for c in cards:
            zero_copay = c.mandatory_copay_pct == 0.0 and c.policy_category != "personal_accident"
            copay_cells[c.doc_id] = ComparisonCell(
                doc_id=c.doc_id,
                display_value=(
                    "0% Mandatory Co-Pay (100% Admissible Claim Paid)"
                    if c.mandatory_copay_pct == 0.0
                    else f"{c.mandatory_copay_pct:.0f}% Mandatory Co-Pay on every claim"
                ),
                sentiment="positive" if zero_copay else "warning",
                is_winner=zero_copay,
                citation=c.feature_citations.get("copay"),
            )
        rows.append(
            ComparisonRow(
                parameter_key="copay",
                parameter_label="6. Mandatory Co-Payment / Cost Sharing",
                consumer_tooltip="Percentage of every hospital bill that you must pay out of your own pocket even after waiting periods.",
                cells=copay_cells,
            )
        )

        # 7. Consumables / Non-Medical Expenses Cover
        cons_cells: dict[str, ComparisonCell] = {}
        for c in cards:
            cons_cells[c.doc_id] = ComparisonCell(
                doc_id=c.doc_id,
                display_value=(
                    f"✅ Covered In-Built ({c.consumables_note})"
                    if c.consumables_covered
                    else f"❌ Not In-Built ({c.consumables_note})"
                ),
                sentiment="positive" if c.consumables_covered else "warning",
                is_winner=c.consumables_covered,
                citation=c.feature_citations.get("consumables"),
            )
        rows.append(
            ComparisonRow(
                parameter_key="consumables",
                parameter_label="7. Non-Medical Consumables Cover (PPE, Gloves, Syringes)",
                consumer_tooltip="Consumables typically account for 8-12% of an Indian private hospital bill. In-built cover prevents surprise discharge deductions.",
                cells=cons_cells,
            )
        )

        # 8. Restoration / Recharge Benefit
        rest_cells: dict[str, ComparisonCell] = {}
        for c in cards:
            has_rest = "100%" in c.restoration_benefit
            rest_cells[c.doc_id] = ComparisonCell(
                doc_id=c.doc_id,
                display_value=c.restoration_benefit,
                sentiment="positive" if has_rest else "warning",
                is_winner=has_rest and "partial" in c.restoration_benefit.lower(),
                citation=c.feature_citations.get("restoration"),
            )
        rows.append(
            ComparisonRow(
                parameter_key="restoration",
                parameter_label="8. Sum Insured Restoration / Backup Benefit",
                consumer_tooltip="Refills your Sum Insured by 100% if a major hospitalization exhausts your cover mid-year—essential for a family of 5.",
                cells=rest_cells,
            )
        )

        # 9. No-Claim / Cumulative Bonus
        ncb_cells: dict[str, ComparisonCell] = {}
        for c in cards:
            high_ncb = "50%" in c.no_claim_bonus_note
            ncb_cells[c.doc_id] = ComparisonCell(
                doc_id=c.doc_id,
                display_value=c.no_claim_bonus_note,
                sentiment="positive" if high_ncb else "neutral",
                is_winner=high_ncb,
                citation=c.feature_citations.get("no_claim_bonus"),
            )
        rows.append(
            ComparisonRow(
                parameter_key="no_claim_bonus",
                parameter_label="9. No-Claim / Guaranteed Renewal Bonus",
                consumer_tooltip="Annual increase in your base Sum Insured for each year without claims (or guaranteed under Plus Benefit).",
                cells=ncb_cells,
            )
        )

        # 10. Pre/Post Hospitalization & AYUSH
        ayush_cells: dict[str, ComparisonCell] = {}
        for c in cards:
            has_180 = "180" in c.pre_post_hospitalization
            ayush_cells[c.doc_id] = ComparisonCell(
                doc_id=c.doc_id,
                display_value=f"{c.pre_post_hospitalization} | AYUSH: {c.ayush_coverage}",
                sentiment="positive" if has_180 else "neutral",
                is_winner=has_180,
                citation=c.feature_citations.get("pre_post_hosp"),
            )
        rows.append(
            ComparisonRow(
                parameter_key="pre_post_ayush",
                parameter_label="10. Pre/Post-Hospitalization & AYUSH In-Patient Cover",
                consumer_tooltip="Covers diagnostic tests before admission, follow-up medicines after discharge, and AYUSH treatments.",
                cells=ayush_cells,
            )
        )

        return rows

    def compare(
        self,
        doc_ids: list[str] | None = None,
        profile: ApplicantProfile | None = None,
    ) -> PolicyComparisonResponse:
        user_profile = profile or ApplicantProfile()
        selected_ids = doc_ids or [c.doc_id for c in list_policy_cards(include_accident=False)]
        cards = [get_policy_card(did) for did in selected_ids]
        premiums = {
            c.doc_id: self.premium_calc.calculate_premium(c.doc_id, user_profile) for c in cards
        }
        rows = self.build_comparison_rows(cards, premiums)
        sim = self.claim_sim.simulate(
            claimed_bill_inr=150_000,
            hospital_room_rent_per_day_inr=8_000,
            days_hospitalized=3,
            procedure_type="general_hospitalization",
            sum_insured_inr=user_profile.target_sum_insured_inr,
            doc_ids=selected_ids,
        )

        summary = (
            f"Compared {len(cards)} IRDAI policies for Age {user_profile.proposer_age}, "
            f"Family of {user_profile.family_size} (Target SI ₹{user_profile.target_sum_insured_inr // 100_000} Lakhs). "
            "Comprehensive plans (HDFC ERGO Optima Secure, Tata AIG MediCare Premier) eliminate room-rent proportionate deductions "
            "and cover non-medical consumables in-built, whereas budget plans (Arogya Sanjeevani) reduce annual premium by ~40% "
            "in exchange for a ₹5,000/day room cap and 5% mandatory co-payment."
        )

        return PolicyComparisonResponse(
            profile_used=user_profile,
            compared_policies=cards,
            premiums=premiums,
            comparison_rows=rows,
            claim_simulation=sim,
            fiduciary_summary=summary,
        )
