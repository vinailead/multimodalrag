"""Deterministic rule-based intent routing and compound-query decomposition.

Used as the stub model's behaviour and as the production fallback if the LLM router fails.
"""

from __future__ import annotations

from insurance_mmrag.domain.irdai import (
    INTENT_CUES,
    SUBQUERY_SPLIT_RE,
    TABLE_BOOST_RE,
    find_excl_codes,
    tokenize,
)
from insurance_mmrag.schemas import IntentDraft, SectionType

_SECTION_ORDER = list(SectionType)
_WAITING_CODES = {"Excl01", "Excl02", "Excl03"}
_CONTEXT_ONLY = {SectionType.DEFINITIONS, SectionType.CIS_SUMMARY}


def decompose_query(query: str, max_sub_queries: int = 3) -> list[str]:
    """Split a compound question into atomic sub-questions (bounded)."""
    parts = [p.strip(" ?.,") for p in SUBQUERY_SPLIT_RE.split(query)]
    atomic = [p for p in parts if len(tokenize(p)) >= 2]
    if len(atomic) <= 1:
        return [query.strip()]
    return [p if p.endswith("?") else f"{p}?" for p in atomic[:max_sub_queries]]


def score_sections(text: str) -> dict[SectionType, int]:
    scores: dict[SectionType, int] = {}
    for section, pattern in INTENT_CUES:
        hits = len(pattern.findall(text))
        if hits:
            scores[section] = hits
    return scores


def rule_based_intent(query: str, max_sub_queries: int = 3) -> IntentDraft:
    scores = score_sections(query)
    codes = find_excl_codes(query)
    if codes:
        scores[SectionType.EXCLUSIONS] = scores.get(SectionType.EXCLUSIONS, 0) + 2
        if _WAITING_CODES.intersection(codes):
            scores[SectionType.WAITING_PERIODS] = scores.get(SectionType.WAITING_PERIODS, 0) + 3
    if not scores:
        scores = {SectionType.BASE_COVERAGE: 1, SectionType.CIS_SUMMARY: 1}

    ordered = sorted(scores, key=lambda s: (-scores[s], _SECTION_ORDER.index(s)))
    targets = ordered[:4]
    if (
        SectionType.WAITING_PERIODS in targets or SectionType.EXCLUSIONS in targets
    ) and SectionType.DEFINITIONS not in targets:
        targets.append(SectionType.DEFINITIONS)

    sub_queries = decompose_query(query, max_sub_queries)
    substantive = [s for s in targets if s not in _CONTEXT_ONLY]
    table_boost = bool(TABLE_BOOST_RE.search(query))
    pro = len(substantive) >= 3 and len(sub_queries) >= 2
    rationale = (
        f"Matched cues for {', '.join(s.value for s in ordered)}"
        f"{'; clause codes ' + ', '.join(codes) if codes else ''}"
        f"{'; numeric/limit terms -> table boost' if table_boost else ''}"
        f"{'; multi-section compound query -> Pro escalation' if pro else ''}."
    )
    return IntentDraft(
        primary_section=ordered[0],
        target_sections=targets,
        detected_clause_codes=codes,
        sub_queries=sub_queries,
        requires_table_boost=table_boost,
        requires_pro_escalation=pro,
        rationale=rationale,
    )
