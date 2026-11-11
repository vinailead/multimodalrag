"""Indicative Actuarial Premium Rate-Card & Family Floater Portfolio-Split Engine."""

from __future__ import annotations

from insurance_mmrag.domain.policy_catalog import get_policy_card
from insurance_mmrag.schemas import ApplicantProfile, PortfolioSplitOption, PremiumBreakdown

# Base annual rate in INR for 1 Adult at ₹10,00,000 Sum Insured (Zone B baseline before GST)
_AGE_BAND_BASE_10L: list[tuple[int, int, int]] = [
    (18, 25, 7_200),
    (26, 30, 8_400),
    (31, 35, 9_800),
    (36, 40, 11_900),
    (41, 45, 14_800),
    (46, 50, 19_200),
    (51, 55, 25_600),
    (56, 60, 33_800),
    (61, 65, 44_500),
    (66, 99, 58_000),
]

_PRODUCT_MULTIPLIERS: dict[str, float] = {
    "hdfc_ergo_optima_secure": 1.16,
    "tata_aig_medicare_premier": 1.12,
    "bajaj_allianz_health_guard": 0.96,
    "godigit_health_plus": 0.90,
    "arogya_sanjeevani_national": 0.66,
    "saral_suraksha_hdfc_ergo": 0.12,
}


def _base_rate_for_age(age: int) -> int:
    clamped = max(18, min(99, age))
    for low, high, rate in _AGE_BAND_BASE_10L:
        if low <= clamped <= high:
            return rate
    return 58_000


def _si_scaling_factor(sum_insured_inr: int) -> float:
    if sum_insured_inr <= 300_000:
        return 0.56
    if sum_insured_inr <= 500_000:
        return 0.72
    if sum_insured_inr <= 1_000_000:
        return 1.00
    if sum_insured_inr <= 1_500_000:
        return 1.24
    if sum_insured_inr <= 2_000_000:
        return 1.44
    if sum_insured_inr <= 2_500_000:
        return 1.62
    return 2.15


class PremiumCalculator:
    """Calculates transparent, GST-inclusive indicative premiums & portfolio-split savings."""

    def calculate_premium(
        self,
        doc_id: str,
        profile: ApplicantProfile,
        override_member_count: int | None = None,
        override_pricing_age: int | None = None,
    ) -> PremiumBreakdown:
        card = get_policy_card(doc_id)
        member_count = (
            override_member_count if override_member_count is not None else profile.family_size
        )

        # Determine effective Sum Insured supported by the policy
        target_si = profile.target_sum_insured_inr
        if doc_id == "arogya_sanjeevani_national" and target_si > 1_000_000:
            effective_si = 1_000_000
        else:
            effective_si = target_si

        # Determine pricing age (Indian Family Floaters price off the ELDEST member)
        if override_pricing_age is not None:
            pricing_age = override_pricing_age
        elif profile.eldest_member_age is not None:
            pricing_age = max(profile.proposer_age, profile.eldest_member_age)
        elif profile.includes_parents:
            pricing_age = max(profile.proposer_age + 28, 55)
        else:
            pricing_age = profile.proposer_age

        age_base_10l = _base_rate_for_age(pricing_age)
        si_factor = _si_scaling_factor(effective_si)
        prod_mult = _PRODUCT_MULTIPLIERS.get(doc_id, 1.0)

        base_annual = round(age_base_10l * si_factor * prod_mult)

        # Family Floater load: 2nd member (spouse/co-adult) adds 28%, additional members add 16% each
        if member_count <= 1:
            floater_load = 0
        else:
            additional = member_count - 1
            floater_load = round(base_annual * (0.28 + max(0, additional - 1) * 0.16))

        subtotal = base_annual + floater_load

        # City Tier Zone adjustment
        city_tier = profile.city_tier or "tier_1"
        if city_tier == "tier_1":
            city_adj = round(subtotal * 0.08)
        elif city_tier == "tier_3":
            city_adj = -round(subtotal * 0.05)
        else:
            city_adj = 0

        # Healthy Lifestyle (Non-smoker & Non-drinker) Discount vs Smoker Loading
        notes: list[str] = []
        if not profile.is_smoker and not profile.is_drinker:
            disc_pct = card.healthy_lifestyle_discount_pct
            healthy_disc = round((subtotal + city_adj) * (disc_pct / 100.0))
            smoker_load = 0
            if healthy_disc > 0:
                notes.append(
                    f"Applied {disc_pct:.1f}% Non-Smoker & Non-Drinker Healthy Lifestyle Discount (-₹{healthy_disc:,}/yr)."
                )
        else:
            healthy_disc = 0
            smoker_load = (
                round((subtotal + city_adj) * 0.12)
                if card.policy_category != "personal_accident"
                else 0
            )
            if smoker_load > 0:
                notes.append(
                    f"Includes +12% Tobacco/Alcohol underwriting loading (+₹{smoker_load:,}/yr)."
                )

        if pricing_age > profile.proposer_age and member_count > 1:
            notes.append(
                f"Priced at eldest member age ({pricing_age} yrs) per IRDAI Family Floater underwriting norms."
            )

        if doc_id == "arogya_sanjeevani_national" and profile.target_sum_insured_inr > 1_000_000:
            notes.append(
                "Capped at ₹10,00,000 maximum Sum Insured per IRDAI Arogya Sanjeevani mandate."
            )

        net_before_gst = max(500, subtotal + city_adj - healthy_disc + smoker_load)
        gst_amount = round(net_before_gst * 0.18)
        total_annual = net_before_gst + gst_amount
        monthly_emi = round(total_annual / 12)

        effective_day_1_cover = round(effective_si * card.day_1_cover_multiplier)
        lakhs = max(1.0, effective_day_1_cover / 100_000.0)
        cost_per_lakh = round(total_annual / lakhs)

        return PremiumBreakdown(
            doc_id=doc_id,
            policy_name=card.short_name,
            sum_insured_inr=effective_si,
            effective_day_1_cover_inr=effective_day_1_cover,
            pricing_age_used=pricing_age,
            member_count=member_count,
            city_tier=city_tier,
            base_annual_premium_inr=base_annual,
            floater_member_load_inr=floater_load,
            city_zone_adjustment_inr=city_adj,
            healthy_lifestyle_discount_inr=healthy_disc,
            smoker_loading_inr=smoker_load,
            net_premium_before_gst_inr=net_before_gst,
            gst_18_pct_inr=gst_amount,
            total_annual_premium_inr=total_annual,
            monthly_emi_inr=monthly_emi,
            cost_per_lakh_cover_inr=cost_per_lakh,
            pricing_notes=notes,
        )

    def evaluate_portfolio_split(
        self,
        profile: ApplicantProfile,
        primary_doc_id: str = "hdfc_ergo_optima_secure",
        parent_doc_id: str = "tata_aig_medicare_premier",
    ) -> PortfolioSplitOption:
        """Compare a single combined family floater against splitting young nuclear members and parents."""
        assumed_parent_age = (
            max(profile.eldest_member_age, 55)
            if profile.eldest_member_age and profile.eldest_member_age >= 48
            else max(profile.proposer_age + 28, 55)
        )
        parents_in_family = bool(
            profile.includes_parents
            or (profile.eldest_member_age is not None and profile.eldest_member_age >= 48)
            or (profile.includes_parents is None and profile.family_size >= 4)
        )

        # Single combined floater when parents are included in one policy
        single_combined = self.calculate_premium(
            primary_doc_id,
            profile,
            override_member_count=profile.family_size,
            override_pricing_age=assumed_parent_age if parents_in_family else profile.proposer_age,
        )

        # Split Portfolio: Policy A (Young Nuclear: e.g. 3 members at age 26) + Policy B (2 Parents at age 55)
        young_members = max(1, profile.family_size - 2) if profile.family_size >= 3 else 1
        parent_members = min(2, max(1, profile.family_size - young_members))

        young_floater = self.calculate_premium(
            primary_doc_id,
            profile,
            override_member_count=young_members,
            override_pricing_age=profile.proposer_age,
        )
        parents_floater = self.calculate_premium(
            parent_doc_id,
            profile,
            override_member_count=parent_members,
            override_pricing_age=assumed_parent_age,
        )

        # If all 5 members are forced into a single floater at age 55 vs splitting 3 young (at age 26) + 2 parents (at age 55)
        single_at_parent_age = self.calculate_premium(
            primary_doc_id,
            profile,
            override_member_count=profile.family_size,
            override_pricing_age=assumed_parent_age,
        )
        split_total = (
            young_floater.total_annual_premium_inr + parents_floater.total_annual_premium_inr
        )
        savings = max(0, single_at_parent_age.total_annual_premium_inr - split_total)
        combined_cover = (
            young_floater.effective_day_1_cover_inr + parents_floater.effective_day_1_cover_inr
        )

        if parents_in_family and profile.family_size >= 3:
            return PortfolioSplitOption(
                recommended_strategy="SPLIT_PORTFOLIO",
                headline=(
                    f"💡 Fiduciary Alert: Split Your Family of {profile.family_size} into 2 Policies "
                    f"(Save ₹{savings:,}/yr & Double Your Coverage Pool!)"
                ),
                explanation=(
                    f"In Indian health insurance, Family Floater premiums are priced on the ELDEST member's age. "
                    f"Adding parents (aged ~{assumed_parent_age}) into a {profile.proposer_age}-year-old's single floater "
                    f"inflates the premium for all {profile.family_size} members to the {assumed_parent_age}-year age bracket "
                    f"(₹{single_at_parent_age.total_annual_premium_inr:,}/yr). Splitting into Policy 1 for yourself/spouse/kids "
                    f"({young_members} members @ age {profile.proposer_age}: ₹{young_floater.total_annual_premium_inr:,}/yr) + "
                    f"Policy 2 for Parents ({parent_members} members @ age {assumed_parent_age}: ₹{parents_floater.total_annual_premium_inr:,}/yr) "
                    f"reduces total cost to ₹{split_total:,}/yr while giving two separate Sum Insured pools!"
                ),
                single_floater_annual_inr=single_at_parent_age.total_annual_premium_inr,
                split_young_floater_annual_inr=young_floater.total_annual_premium_inr,
                split_parents_floater_annual_inr=parents_floater.total_annual_premium_inr,
                split_total_annual_inr=split_total,
                annual_savings_inr=savings,
                combined_effective_cover_inr=combined_cover,
                key_reasons_to_split=[
                    f"Saves ₹{savings:,}/year by pricing the {young_members} younger members at age {profile.proposer_age} instead of age {assumed_parent_age}.",
                    "Protects your No-Claim Bonus (50%-100% Plus/Cumulative Bonus): routine parent claims won't reset the young family's bonus.",
                    f"Doubles total family protection to ₹{combined_cover // 100_000} Lakhs across two independent restoration pools.",
                    "Allows choosing a 24-month PED waiting period plan (Tata AIG MediCare Premier) specifically for parents.",
                ],
            )

        return PortfolioSplitOption(
            recommended_strategy="SINGLE_FLOATER",
            headline=(
                f"✅ Single Family Floater Recommended for {profile.family_size} Nuclear Member(s) "
                f"(₹{single_combined.total_annual_premium_inr:,}/yr)"
            ),
            explanation=(
                f"Since your family of {profile.family_size} consists of nuclear members in the young age band "
                f"(eldest age {single_combined.pricing_age_used} yrs) without senior parents, a single comprehensive "
                f"Family Floater is the most cost-effective structure at ₹{single_combined.total_annual_premium_inr:,}/yr "
                f"(₹{single_combined.monthly_emi_inr:,}/month)."
            ),
            single_floater_annual_inr=single_combined.total_annual_premium_inr,
            split_young_floater_annual_inr=young_floater.total_annual_premium_inr,
            split_parents_floater_annual_inr=parents_floater.total_annual_premium_inr,
            split_total_annual_inr=split_total,
            annual_savings_inr=0,
            combined_effective_cover_inr=single_combined.effective_day_1_cover_inr,
            key_reasons_to_split=[
                f"All {profile.family_size} members are in a similar young age bracket ({single_combined.pricing_age_used} yrs), maximizing multi-member floater discounts.",
                "Note: If your family of 5 includes parents aged 50+, switch 'Includes Parents' to Yes to unlock Split-Portfolio savings.",
            ],
        )
