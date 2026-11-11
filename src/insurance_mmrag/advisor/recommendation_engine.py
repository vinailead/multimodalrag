"""Conversational Needs-Discovery, Probing Underwriter & Policy Recommendation Engine."""

from __future__ import annotations

import re

from insurance_mmrag.advisor.claim_simulator import ClaimSimulator
from insurance_mmrag.advisor.policy_comparator import PolicyComparator
from insurance_mmrag.domain.policy_catalog import list_policy_cards
from insurance_mmrag.domain.premium_calculator import PremiumCalculator
from insurance_mmrag.schemas import (
    AdvisorRecommendationResponse,
    ApplicantProfile,
    PolicyFeatureCard,
    PremiumBreakdown,
    ProbingQuestion,
    RankedPolicyRecommendation,
)

_RECOMMENDATION_CUE_RE = re.compile(
    r"\b("
    r"best\s+policy|best\s+plan|best\s+health|recommend|suggest|which\s+policy|which\s+plan|"
    r"suitable\s+policy|good\s+policy|family\s+of\s+\d+|looking\s+to\s+select|Looking\s+for\s+a\s+policy|"
    r"compare\s+policies|compare\s+plans|non[- ]?smoker|non[- ]?drinker|what\s+policy\s+should\s+i\s+buy"
    r")\b",
    re.IGNORECASE,
)


def is_advisory_or_comparison_query(query: str) -> bool:
    """Detect whether a user query is asking for policy recommendation, selection, or comparison."""
    return bool(_RECOMMENDATION_CUE_RE.search(query))


class RecommendationEngine:
    """Extracts user underwriting profile, generates probing questions, and ranks policies."""

    def __init__(self) -> None:
        self.premium_calc = PremiumCalculator()
        self.comparator = PolicyComparator()
        self.claim_sim = ClaimSimulator()

    def extract_profile_from_query(
        self,
        query: str,
        explicit_profile: ApplicantProfile | None = None,
    ) -> tuple[ApplicantProfile, set[str]]:
        """Parse natural-language query into an ApplicantProfile and track explicitly filled slots."""
        q = query.lower()
        filled: set[str] = set()

        base = explicit_profile.model_copy() if explicit_profile else ApplicantProfile()
        if explicit_profile is not None:
            if explicit_profile.includes_parents is not None:
                filled.add("family_composition")
            if explicit_profile.eldest_member_age is not None:
                filled.add("eldest_member_age")
            if explicit_profile.has_pre_existing_diseases is not None:
                filled.add("pre_existing_diseases")
            if explicit_profile.city_tier is not None:
                filled.add("city_tier")
            if explicit_profile.budget_priority is not None:
                filled.add("budget_priority")

        # 1. Proposer Age
        age_match = (
            re.search(r"age\s*(?:is|of|:)?\s*(\d{2})\b", q)
            or re.search(r"\b(\d{2})\s*(?:years?\s*old|yrs?\s*old|yo\b|yr\b)", q)
            or re.search(r"\bi\s+am\s+(\d{2})\b", q)
        )
        if age_match:
            age_val = int(age_match.group(1))
            if 18 <= age_val <= 99:
                base.proposer_age = age_val
                filled.add("proposer_age")

        # 2. Family Size
        fam_match = (
            re.search(r"family\s+of\s+(\d+)\b", q)
            or re.search(r"\b(\d+)\s+family\s+members?\b", q)
            or re.search(r"\b(\d+)\s+members?\b", q)
        )
        if fam_match:
            fsize = int(fam_match.group(1))
            if 1 <= fsize <= 10:
                base.family_size = fsize
                filled.add("family_size")

        # 3. Smoker / Drinker status
        if re.search(r"non[- ]?smoker|do\s*n[o']?t\s+smoke|no\s+smoking|never\s+smoked", q):
            base.is_smoker = False
            filled.add("is_smoker")
        elif re.search(r"\bsmoker\b|\bsmoking\b", q):
            base.is_smoker = True
            filled.add("is_smoker")

        if re.search(
            r"non[- ]?drinker|teetotaler|do\s*n[o']?t\s+drink|no\s+alcohol|never\s+drink", q
        ):
            base.is_drinker = False
            filled.add("is_drinker")
        elif re.search(r"\bdrinker\b|\balcohol\b", q):
            base.is_drinker = True
            filled.add("is_drinker")

        # 4. Parents / Eldest Member Age
        eldest_match = re.search(
            r"(?:eldest|oldest|parent|father|mother)\s*(?:member)?\s*(?:age|aged|is)?\s*(\d{2})\b",
            q,
        )
        if eldest_match:
            e_age = int(eldest_match.group(1))
            if 18 <= e_age <= 99:
                base.eldest_member_age = e_age
                filled.add("eldest_member_age")
                filled.add("family_composition")
                if e_age >= 48:
                    base.includes_parents = True

        if re.search(
            r"no\s+parents|without\s+parents|only\s+spouse|nuclear\s+family|spouse\s+and\s+kids", q
        ):
            base.includes_parents = False
            filled.add("family_composition")
        elif re.search(r"\bparents?\b|\bfather\b|\bmother\b|\bsenior\b|\bmom\b|\bdad\b", q):
            base.includes_parents = True
            filled.add("family_composition")

        # 5. Pre-Existing Diseases (PED)
        ped_list: list[str] = list(base.pre_existing_conditions)
        for cond, label in [
            ("diabet", "Diabetes"),
            ("hypertension|high bp|\\bbp\\b", "Hypertension (BP)"),
            ("thyroid", "Thyroid"),
            ("asthma", "Asthma"),
            ("cataract", "Cataract"),
            ("cardiac|heart", "Cardiac Condition"),
        ]:
            if re.search(cond, q) and label not in ped_list:
                ped_list.append(label)

        if re.search(
            r"no\s+ped|no\s+pre[- ]?existing|all\s+healthy|no\s+medical|without\s+ped|none\s+have\s+ped",
            q,
        ):
            base.has_pre_existing_diseases = False
            base.pre_existing_conditions = []
            filled.add("pre_existing_diseases")
        elif ped_list or re.search(r"pre[- ]?existing|\bped\b|chronic", q):
            base.has_pre_existing_diseases = True
            base.pre_existing_conditions = ped_list or ["Declared Pre-Existing Condition"]
            filled.add("pre_existing_diseases")

        # 6. City Tier
        if re.search(
            r"tier[- ]?1|metro|mumbai|delhi|bangalore|bengaluru|chennai|hyderabad|pune|kolkata|gurgaon|noida",
            q,
        ):
            base.city_tier = "tier_1"
            filled.add("city_tier")
        elif re.search(r"tier[- ]?2|jaipur|lucknow|indore|coimbatore|kochi|chandigarh|nagpur", q):
            base.city_tier = "tier_2"
            filled.add("city_tier")
        elif re.search(r"tier[- ]?3|small\s+town|rural", q):
            base.city_tier = "tier_3"
            filled.add("city_tier")

        # 7. Target Sum Insured
        si_match = re.search(r"(\d{1,2})\s*(?:lakhs?|lacs?|l\b)", q)
        if si_match:
            lakhs_num = int(si_match.group(1))
            if 1 <= lakhs_num <= 100:
                base.target_sum_insured_inr = lakhs_num * 100_000
                filled.add("target_sum_insured")

        # 8. Budget / Priority Preference
        if re.search(r"budget|cheapest|lowest\s+premium|low\s+cost|arogya", q):
            base.budget_priority = "budget_low_premium"
            filled.add("budget_priority")
        elif re.search(r"value|balanced|moderate\s+premium", q):
            base.budget_priority = "value_balanced"
            filled.add("budget_priority")
        elif re.search(
            r"comprehensive|zero\s+co[- ]?pay|no\s+room\s+rent|best\s+coverage|maximum\s+cover", q
        ):
            base.budget_priority = "comprehensive_zero_copay"
            filled.add("budget_priority")

        return base, filled

    def build_probing_questions(
        self,
        profile: ApplicantProfile,
        filled_slots: set[str],
    ) -> list[ProbingQuestion]:
        """Generate targeted follow-up underwriting questions for missing slots."""
        questions: list[ProbingQuestion] = []

        if "family_composition" not in filled_slots and profile.family_size >= 2:
            questions.append(
                ProbingQuestion(
                    question_id="probe_family_composition",
                    slot_name="family_composition",
                    question_text=(
                        f"1. Who are the {profile.family_size} members in your family, and what is the age of the eldest member?"
                    ),
                    why_it_matters=(
                        "In Indian health insurance, Family Floater premiums are priced on the ELDEST member's age. "
                        "If parents aged 50+ are included with a 26-year-old, splitting into 2 policies (Young Nuclear + Parent Plan) "
                        "saves ~30-40% in annual premium and protects your No-Claim Bonus!"
                    ),
                    options=[
                        "Self + Spouse + Kids only (Eldest age <= 35 yrs)",
                        "Includes Parents aged 50-58 yrs (Recommend Split Portfolio)",
                        "Includes Senior Citizen Parents aged 60+ yrs",
                    ],
                    current_value=(
                        "Includes Parents"
                        if profile.includes_parents
                        else (
                            "Nuclear Only"
                            if profile.includes_parents is False
                            else "Not specified yet"
                        )
                    ),
                )
            )

        if "pre_existing_diseases" not in filled_slots:
            questions.append(
                ProbingQuestion(
                    question_id="probe_ped",
                    slot_name="pre_existing_diseases",
                    question_text=(
                        "2. Does any family member have a Pre-Existing Disease (Diabetes, BP, Thyroid, Asthma) or upcoming surgery (e.g., Cataract)?"
                    ),
                    why_it_matters=(
                        "If any member has a pre-existing condition, choosing a policy with a 24-month PED waiting period "
                        "(Tata AIG MediCare Premier) instead of a 36-48 month waiting period (Code-Excl01) unlocks coverage 1-2 years earlier."
                    ),
                    options=[
                        "No Pre-Existing Diseases (All members healthy)",
                        "Yes - Diabetes / Hypertension / Thyroid (Prioritize 24-mo PED wait)",
                        "Yes - Planned Cataract / Hernia / Joint Surgery (Check Excl02 sub-limits)",
                    ],
                    current_value=(
                        "Yes"
                        if profile.has_pre_existing_diseases
                        else (
                            "No"
                            if profile.has_pre_existing_diseases is False
                            else "Not specified yet"
                        )
                    ),
                )
            )

        if "city_tier" not in filled_slots:
            questions.append(
                ProbingQuestion(
                    question_id="probe_city_tier",
                    slot_name="city_tier",
                    question_text=(
                        "3. Which City Tier will your family primarily use for hospitalization, and what Sum Insured do you prefer?"
                    ),
                    why_it_matters=(
                        "Private single AC rooms in Tier-1 Metros (Mumbai, Bengaluru, Delhi, Chennai, Hyderabad) cost ₹8,000-₹15,000/day. "
                        "Buying a policy with a ₹5,000/day room cap in a Metro causes a 35%+ Proportionate Deduction on your entire surgery bill!"
                    ),
                    options=[
                        "Tier-1 Metro (Recommend ₹10L-₹20L Cover with Zero Room Rent Cap)",
                        "Tier-2 City (Recommend ₹10L Cover with Single Private Room)",
                        "Tier-3 Town (₹5L-₹10L Budget Cover)",
                    ],
                    current_value=profile.city_tier or "Assuming Tier-1 Metro (Default ₹10L)",
                )
            )

        if "budget_priority" not in filled_slots:
            questions.append(
                ProbingQuestion(
                    question_id="probe_budget_priority",
                    slot_name="budget_priority",
                    question_text=(
                        "4. What is your priority between Zero Out-of-Pocket Hospital Claims vs. Lowest Annual Premium?"
                    ),
                    why_it_matters=(
                        "Flagship plans (HDFC ERGO Optima Secure, Tata AIG MediCare Premier) cover non-medical consumables (PPE, syringes, gloves) "
                        "and have 0% co-pay, whereas standard budget plans (Arogya Sanjeevani) cut premium by ~40% but require a 5% co-pay."
                    ),
                    options=[
                        "Comprehensive Zero-Deduction (0% Co-pay, No Room Cap, Consumables Covered)",
                        "Balanced Value Floater (Single Private Room, Moderate Premium)",
                        "Strict Budget (Lowest Annual Premium, Accept 5% Co-pay & Room Sub-limit)",
                    ],
                    current_value=profile.budget_priority or "Comprehensive / Best Fit",
                )
            )

        return questions

    def _score_policy(
        self,
        card: PolicyFeatureCard,
        profile: ApplicantProfile,
    ) -> tuple[float, float, float, float, float, list[str], list[str]]:
        """Compute match_score and sub-scores along with personalized pros and watch-outs."""
        # Coverage score (0-100)
        cov_score = 75.0
        if card.day_1_cover_multiplier >= 2.0:
            cov_score += 18.0
        elif "200%" in card.no_claim_bonus_note:
            cov_score += 12.0
        elif "100%" in card.restoration_benefit:
            cov_score += 8.0
        if card.consumables_covered:
            cov_score += 7.0
        cov_score = min(100.0, cov_score)

        # Waiting period score (0-100)
        if card.ped_waiting_months <= 24:
            wait_score = 96.0
        elif card.ped_waiting_months <= 36:
            wait_score = 84.0
        else:
            wait_score = 65.0

        # Room rent & zero co-pay score (0-100)
        if not card.has_room_rent_cap and not card.proportionate_deduction_applies:
            room_score = 98.0
        elif not card.has_room_rent_cap:
            room_score = 90.0
        else:
            room_score = 52.0
        if card.mandatory_copay_pct > 0:
            room_score -= 12.0

        # Value / Budget score (0-100)
        if card.doc_id == "arogya_sanjeevani_national":
            val_score = 96.0
        elif card.doc_id in {"godigit_health_plus", "bajaj_allianz_health_guard"}:
            val_score = 91.0
        else:
            val_score = 86.0

        # Weight according to user profile & priorities
        if profile.budget_priority == "budget_low_premium":
            match = 0.20 * cov_score + 0.15 * wait_score + 0.15 * room_score + 0.50 * val_score
            if card.doc_id == "arogya_sanjeevani_national":
                match += 12.0
        elif profile.budget_priority == "value_balanced":
            match = 0.25 * cov_score + 0.20 * wait_score + 0.25 * room_score + 0.30 * val_score
            if card.doc_id in {"bajaj_allianz_health_guard", "godigit_health_plus"}:
                match += 6.0
        elif profile.has_pre_existing_diseases:
            match = 0.28 * cov_score + 0.38 * wait_score + 0.22 * room_score + 0.12 * val_score
        else:
            match = 0.36 * cov_score + 0.20 * wait_score + 0.30 * room_score + 0.14 * val_score

        match = round(min(99.0, max(50.0, match)), 1)

        why_you: list[str] = list(card.key_strengths[:3])
        if (
            not profile.is_smoker
            and not profile.is_drinker
            and card.healthy_lifestyle_discount_pct > 0
        ):
            why_you.insert(
                0,
                f"Rewards your Age {profile.proposer_age} Non-Smoker & Non-Drinker profile with a {card.healthy_lifestyle_discount_pct:.1f}% Healthy Lifestyle premium discount.",
            )
        if profile.family_size >= 3 and "100%" in card.restoration_benefit:
            why_you.append(
                f"100% Automatic Sum Insured Restoration ensures all {profile.family_size} family members remain protected even after a major claim."
            )

        watch_outs = list(card.fine_print_warnings)
        return (
            match,
            round(cov_score, 1),
            round(wait_score, 1),
            round(room_score, 1),
            round(val_score, 1),
            why_you,
            watch_outs,
        )

    def recommend(
        self,
        query: str,
        explicit_profile: ApplicantProfile | None = None,
    ) -> AdvisorRecommendationResponse:
        """Execute full needs-discovery, probing question generation, ranking, and comparison."""
        profile, filled_slots = self.extract_profile_from_query(query, explicit_profile)
        probing_questions = self.build_probing_questions(profile, filled_slots)
        needs_probing = len(probing_questions) > 0

        # Completeness percentage across 6 core underwriting dimensions
        total_dims = 6
        filled_count = min(total_dims, max(2, total_dims - len(probing_questions)))
        completeness_pct = round((filled_count / total_dims) * 100)

        health_cards = list_policy_cards(include_accident=False)
        scored_items: list[
            tuple[float, PolicyFeatureCard, tuple[float, float, float, float, list[str], list[str]]]
        ] = []
        for card in health_cards:
            m_score, c_sc, w_sc, r_sc, v_sc, pros, cons = self._score_policy(card, profile)
            scored_items.append((m_score, card, (c_sc, w_sc, r_sc, v_sc, pros, cons)))

        scored_items.sort(key=lambda x: -x[0])

        badges = [
            "🏆 #1 Best Overall Match",
            "💎 #2 Best for Shorter PED Wait & Bonus",
            "⚖️ #3 Best Balanced Value Floater",
            "⚡ #4 Best Digital Young Family Plan",
            "💰 #5 Best Low-Premium IRDAI Standard",
        ]

        ranked_policies: list[RankedPolicyRecommendation] = []
        premiums_map: dict[str, PremiumBreakdown] = {}
        ordered_cards: list[PolicyFeatureCard] = []

        for idx, (m_score, card, (c_sc, w_sc, r_sc, v_sc, pros, cons)) in enumerate(scored_items):
            prem = self.premium_calc.calculate_premium(card.doc_id, profile)
            premiums_map[card.doc_id] = prem
            ordered_cards.append(card)
            ranked_policies.append(
                RankedPolicyRecommendation(
                    rank=idx + 1,
                    badge=badges[idx] if idx < len(badges) else f"#{idx + 1} Option",
                    match_score=m_score,
                    coverage_score=c_sc,
                    waiting_period_score=w_sc,
                    room_rent_score=r_sc,
                    value_score=v_sc,
                    feature_card=card,
                    premium=prem,
                    why_recommended_for_you=pros,
                    watch_out_for=cons,
                )
            )

        split_advice = self.premium_calc.evaluate_portfolio_split(
            profile,
            primary_doc_id=ranked_policies[0].feature_card.doc_id,
            parent_doc_id="tata_aig_medicare_premier",
        )
        comp_rows = self.comparator.build_comparison_rows(ordered_cards, premiums_map)
        claim_sim = self.claim_sim.simulate(
            claimed_bill_inr=150_000,
            hospital_room_rent_per_day_inr=8_000,
            days_hospitalized=3,
            procedure_type="general_hospitalization",
            sum_insured_inr=profile.target_sum_insured_inr,
            doc_ids=[c.doc_id for c in ordered_cards],
        )

        top1 = ranked_policies[0]
        top2 = ranked_policies[1]
        lifestyle_str = (
            "non-smoker & non-drinker (eligible for up to 7.5% Healthy Lifestyle discount)"
            if not profile.is_smoker and not profile.is_drinker
            else "standard underwriting profile"
        )

        exec_lines = [
            f"### 🎯 Personalized Advisory for Age {profile.proposer_age} ({lifestyle_str}), Family of {profile.family_size}",
            "",
            f"1. **Top Recommended Policy ({top1.badge} — {top1.match_score}% Match):** **{top1.feature_card.short_name}** "
            f"at **₹{top1.premium.total_annual_premium_inr:,}/year** (₹{top1.premium.monthly_emi_inr:,}/month incl. 18% GST) "
            f"for **₹{top1.premium.effective_day_1_cover_inr // 100_000} Lakhs usable Day-1 cover** "
            f"(Base ₹{top1.premium.sum_insured_inr // 100_000}L x {top1.feature_card.day_1_cover_multiplier:.0f}X, "
            f"Zero Room-Rent Cap, 0% Co-pay, and In-Built Consumables Cover).",
            f"2. **Runner-Up ({top2.badge} — {top2.match_score}% Match):** **{top2.feature_card.short_name}** "
            f"at **₹{top2.premium.total_annual_premium_inr:,}/year** (₹{top2.premium.monthly_emi_inr:,}/month) — "
            f"ideal if any family member needs a shorter **{top2.feature_card.ped_waiting_months}-month Pre-Existing Disease (Excl01) waiting period**.",
            f"3. **⚠️ Critical Family-of-{profile.family_size} Structuring Advice ({split_advice.recommended_strategy.replace('_', ' ')}):** "
            f"{split_advice.explanation}",
        ]
        if needs_probing:
            exec_lines.append("")
            exec_lines.append(
                f"**🔍 Answer {len(probing_questions)} Quick Follow-Up Questions Below** to lock in your exact family ages, "
                "pre-existing conditions, and city tier!"
            )

        return AdvisorRecommendationResponse(
            query=query,
            extracted_profile=profile,
            needs_probing=needs_probing,
            completeness_pct=completeness_pct,
            probing_questions=probing_questions,
            executive_advisory_summary="\n".join(exec_lines),
            portfolio_split_advice=split_advice,
            ranked_policies=ranked_policies,
            comparison_matrix=comp_rows,
            claim_simulation=claim_sim,
        )
