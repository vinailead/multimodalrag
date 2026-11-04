"""Pre-retrieval query intent classifier, CRAG sub-query decomposer, and filter builder."""

from __future__ import annotations

from insurance_mmrag.domain.intent_rules import rule_based_intent
from insurance_mmrag.llm.gateway import ModelGateway
from insurance_mmrag.schemas import IntentDraft, QueryIntentClassification


class IntentRouter:
    """Classifies user intent, scopes section filters, and decomposes compound queries for CRAG."""

    def __init__(
        self, gateway: ModelGateway, model: str = "gemini-2.5-flash", max_sub_queries: int = 3
    ) -> None:
        self.gateway = gateway
        self.model = model
        self.max_sub_queries = max_sub_queries

    def classify_intent(self, user_query: str) -> QueryIntentClassification:
        clean_query, _pii_cats, _ = self.gateway.guard_text(user_query)

        try:
            res = self.gateway.generate(
                task="intent_route",
                model=self.model,
                instruction=(
                    "Classify this Indian health/motor insurance search query into target IRDAI section types. "
                    "Extract any explicit clause/exclusion codes (e.g. Excl01, Excl02). "
                    "If the query is compound (asks about multiple things like coverage, waiting period, sub-limits), "
                    "decompose it into up to 3 atomic sub-queries for multi-hop retrieval. "
                    "Set requires_table_boost=true if the query asks about numerical limits, sum insured slabs, or co-pay."
                ),
                schema=IntentDraft,
                operation="retrieval.intent_route",
                user_query=clean_query,
                hints={"max_sub_queries": str(self.max_sub_queries)},
            )
            draft = res.parsed
        except Exception:
            # Deterministic rule-based fallback
            draft = rule_based_intent(clean_query, self.max_sub_queries)

        return QueryIntentClassification(
            original_query=user_query,
            redacted_query=clean_query,
            primary_section=draft.primary_section,
            target_sections=draft.target_sections,
            detected_clause_codes=draft.detected_clause_codes,
            sub_queries=draft.sub_queries,
            requires_table_boost=draft.requires_table_boost,
            requires_pro_escalation=draft.requires_pro_escalation,
            rationale=draft.rationale,
        )
