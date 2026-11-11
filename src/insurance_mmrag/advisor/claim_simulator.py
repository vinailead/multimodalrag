"""Out-of-Pocket Hospital Bill & Claim Deduction Simulator across Indian Insurance Policies."""

from __future__ import annotations

from insurance_mmrag.domain.policy_catalog import get_policy_card, list_policy_cards
from insurance_mmrag.schemas import ClaimSimulationItem, ClaimSimulationResponse


class ClaimSimulator:
    """Simulates real-world Indian hospital bill settlement across multiple policies."""

    def simulate(
        self,
        claimed_bill_inr: int = 150_000,
        hospital_room_rent_per_day_inr: int = 8_000,
        days_hospitalized: int = 3,
        procedure_type: str = "general_hospitalization",
        sum_insured_inr: int = 1_000_000,
        doc_ids: list[str] | None = None,
    ) -> ClaimSimulationResponse:
        target_ids = doc_ids or [c.doc_id for c in list_policy_cards(include_accident=False)]
        results: list[ClaimSimulationItem] = []

        proc_lower = procedure_type.lower()
        is_cataract = "cataract" in proc_lower
        is_accident = "accident" in proc_lower

        for doc_id in target_ids:
            card = get_policy_card(doc_id)

            # Personal Accident policy only covers accidental injuries, not illness/surgeries
            if card.policy_category == "personal_accident" and not is_accident:
                results.append(
                    ClaimSimulationItem(
                        doc_id=doc_id,
                        policy_name=card.policy_name,
                        short_name=card.short_name,
                        claimed_bill_inr=claimed_bill_inr,
                        room_rent_deduction_inr=0,
                        procedure_sublimit_deduction_inr=claimed_bill_inr,
                        consumables_deduction_inr=0,
                        copay_deduction_inr=0,
                        insurer_payable_inr=0,
                        user_out_of_pocket_inr=claimed_bill_inr,
                        coverage_ratio_pct=0.0,
                        explanation=(
                            "Personal Accident policy covers only external accidental bodily injury, "
                            "not medical illness or planned surgical hospitalizations."
                        ),
                    )
                )
                continue

            # 1. Consumables (IRDAI Annexure-I non-medical items ~8% of hospital bill)
            consumables_ded = 0 if card.consumables_covered else round(claimed_bill_inr * 0.08)
            rem = max(0, claimed_bill_inr - consumables_ded)

            # 2. Room Rent Cap & Proportionate Deduction
            room_ded = 0
            if card.has_room_rent_cap and card.max_room_rent_per_day_inr:
                pct_cap = round(sum_insured_inr * ((card.room_rent_pct_of_si or 2.0) / 100.0))
                eligible_room = min(pct_cap, card.max_room_rent_per_day_inr)
                if hospital_room_rent_per_day_inr > eligible_room:
                    excess_ratio = (
                        hospital_room_rent_per_day_inr - eligible_room
                    ) / hospital_room_rent_per_day_inr
                    # Proportionate deduction applies to ~75% of the bill (associated medical expenses)
                    room_ded = round(rem * 0.75 * excess_ratio)
            rem = max(0, rem - room_ded)

            # 3. Procedure Sub-limit (e.g. Cataract per-eye cap)
            proc_ded = 0
            if (
                is_cataract
                and card.cataract_max_per_eye_inr is not None
                and rem > card.cataract_max_per_eye_inr
            ):
                proc_ded = rem - card.cataract_max_per_eye_inr
            rem = max(0, rem - proc_ded)

            # 4. Mandatory Co-payment
            copay_ded = round(rem * (card.mandatory_copay_pct / 100.0))
            rem = max(0, rem - copay_ded)

            effective_cover = round(sum_insured_inr * card.day_1_cover_multiplier)
            insurer_pays = min(effective_cover, rem)
            user_oop = claimed_bill_inr - insurer_pays
            ratio_pct = round((insurer_pays / max(1, claimed_bill_inr)) * 100.0, 1)

            reasons: list[str] = []
            if room_ded > 0:
                reasons.append(
                    f"₹{room_ded:,} deducted due to Room Rent Cap (₹{card.max_room_rent_per_day_inr:,}/day max vs ₹{hospital_room_rent_per_day_inr:,}/day room) & Proportionate Deduction"
                )
            if proc_ded > 0:
                reasons.append(
                    f"₹{proc_ded:,} deducted due to Cataract per-eye sub-limit (₹{card.cataract_max_per_eye_inr:,} cap)"
                )
            if consumables_ded > 0:
                reasons.append(
                    f"₹{consumables_ded:,} non-payable consumables (8% Annexure-I items) paid by insured"
                )
            if copay_ded > 0:
                reasons.append(
                    f"₹{copay_ded:,} deducted for {card.mandatory_copay_pct:.0f}% mandatory co-payment"
                )
            if not reasons:
                reasons.append(
                    "Zero out-of-pocket deductions! 100% of bill including consumables & room rent paid by insurer."
                )

            results.append(
                ClaimSimulationItem(
                    doc_id=doc_id,
                    policy_name=card.policy_name,
                    short_name=card.short_name,
                    claimed_bill_inr=claimed_bill_inr,
                    room_rent_deduction_inr=room_ded,
                    procedure_sublimit_deduction_inr=proc_ded,
                    consumables_deduction_inr=consumables_ded,
                    copay_deduction_inr=copay_ded,
                    insurer_payable_inr=insurer_pays,
                    user_out_of_pocket_inr=user_oop,
                    coverage_ratio_pct=ratio_pct,
                    explanation="; ".join(reasons) + ".",
                )
            )

        scenario_label = (
            f"₹{claimed_bill_inr:,} Hospital Bill ({procedure_type.replace('_', ' ').title()}, "
            f"{days_hospitalized} Days @ ₹{hospital_room_rent_per_day_inr:,}/day Room)"
        )
        return ClaimSimulationResponse(
            scenario_title=scenario_label,
            procedure_type=procedure_type,
            claimed_bill_inr=claimed_bill_inr,
            hospital_room_rent_per_day_inr=hospital_room_rent_per_day_inr,
            days_hospitalized=days_hospitalized,
            sum_insured_inr=sum_insured_inr,
            results=results,
        )
