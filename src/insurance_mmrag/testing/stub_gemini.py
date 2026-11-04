"""Deterministic offline stand-in for Gemini used by every unit, integration and E2E test.

It honours the exact `ModelClient` protocol, returns schema-valid structured outputs derived
from the request's evidence/hints, and simulates token usage so FinOps maths is exercised.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import cast

from pydantic import BaseModel

from insurance_mmrag.domain.intent_rules import rule_based_intent
from insurance_mmrag.domain.irdai import classify_heading, find_excl_codes, tokenize
from insurance_mmrag.llm.protocol import (
    EmbeddingResult,
    EvidenceItem,
    GenerationRequest,
    GenerationResult,
    render_prompt,
)
from insurance_mmrag.schemas import (
    IntentDraft,
    LlmGroundedDraft,
    PolicyCoverageSummary,
    SectionClassificationDraft,
    SectionType,
    SyntheticQA,
    TableExtractionDraft,
)

_GENERIC_QUERY_TOKENS = frozenset(
    {"covered", "cover", "policy", "insurance", "plan", "benefit", "get", "applicable", "apply"}
)
_SENTENCE_RE = re.compile(r"(?<=[.;])\s+|\n+")
_NUMERIC_RE = re.compile(r"₹|rs\.?\s*\d|\d+\s*%|lakh|\blimit", re.IGNORECASE)


def _approx_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def _parse_rows(raw: str) -> list[list[str]]:
    data: object = json.loads(raw)
    rows: list[list[str]] = []
    if isinstance(data, list):
        for row in cast(list[object], data):
            if isinstance(row, list):
                rows.append([str(c).strip() for c in cast(list[object], row)])
    return rows


class StubGeminiClient:
    """Deterministic model double. `model_name` reported for FinOps is the requested model."""

    def __init__(self) -> None:
        self.generate_calls = 0
        self.embed_calls = 0

    # ------------------------------------------------------------------ generation
    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.generate_calls += 1
        parsed: BaseModel
        if request.task == "structure_classify":
            parsed = self._classify(request)
        elif request.task == "table_extract":
            parsed = self._extract_table(request)
        elif request.task == "intent_route":
            parsed = self._route(request)
        else:
            parsed = self._ground(request)
        prompt = render_prompt(request)
        return GenerationResult(
            parsed=parsed,
            model=request.model,
            prompt_tokens=_approx_tokens(prompt) + 258 * len(request.images),
            completion_tokens=_approx_tokens(parsed.model_dump_json()),
        )

    @staticmethod
    def _classify(request: GenerationRequest) -> SectionClassificationDraft:
        heading = request.hints.get("heading", "")
        preview = request.hints.get("preview", "")
        section = classify_heading(heading) or classify_heading(preview)
        if section is None:
            return SectionClassificationDraft(
                section_type=SectionType.BASE_COVERAGE, confidence=0.4
            )
        return SectionClassificationDraft(section_type=section, confidence=0.9)

    @staticmethod
    def _extract_table(request: GenerationRequest) -> TableExtractionDraft:
        rows = _parse_rows(request.hints.get("rows_json", "[]"))
        section_title = request.hints.get("section_title", "Policy Table")
        footnotes = [
            ln.strip()
            for ln in request.hints.get("footnotes", "").splitlines()
            if ln.strip().startswith("*")
        ]
        if not rows:
            return TableExtractionDraft(
                title=f"{section_title} (empty table)",
                summary="No tabular content could be extracted.",
                markdown_table="",
                structured_rows=[],
                footnotes=footnotes,
                synthetic_qa_pairs=[],
            )
        header = rows[0]
        body = rows[1:]
        md = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        md.extend("| " + " | ".join(r) + " |" for r in body)
        structured = [
            {header[i]: (r[i] if i < len(r) else "") for i in range(len(header))} for r in body
        ]
        qa: list[SyntheticQA] = []
        for r in body:
            for i in range(1, len(header)):
                if i < len(r) and r[i]:
                    qa.append(
                        SyntheticQA(
                            question=f"What is the {header[i]} for {r[0]}?",
                            answer=f"{header[i]} for {r[0]} is {r[i]}.",
                        )
                    )
        return TableExtractionDraft(
            title=f"{section_title}: {header[0]} vs {', '.join(header[1:4])}",
            summary=(
                f"Table listing {', '.join(header[1:])} across {len(body)} rows "
                f"({', '.join(r[0] for r in body[:4])})."
            ),
            markdown_table="\n".join(md),
            structured_rows=structured,
            footnotes=footnotes,
            synthetic_qa_pairs=qa[:10],
        )

    @staticmethod
    def _route(request: GenerationRequest) -> IntentDraft:
        max_sub = int(request.hints.get("max_sub_queries", "3"))
        return rule_based_intent(request.user_query, max_sub)

    @staticmethod
    def _ground(request: GenerationRequest) -> LlmGroundedDraft:
        q_tokens = {t for t in tokenize(request.user_query) if t not in _GENERIC_QUERY_TOKENS}
        scored: list[tuple[float, EvidenceItem]] = []
        for ev in request.evidence:
            e_tokens = set(tokenize(ev.text))
            overlap = len(q_tokens & e_tokens) / len(q_tokens) if q_tokens else 0.0
            scored.append((overlap, ev))
        scored.sort(key=lambda x: -x[0])
        selected = [ev for score, ev in scored if score >= 0.25][:4]
        if not selected or not q_tokens:
            return LlmGroundedDraft(
                answer="The provided policy evidence does not address this question.",
                coverage_summary=PolicyCoverageSummary(
                    coverage_status="INDETERMINATE",
                    waiting_period_details="Not specified in retrieved evidence.",
                    applicable_sub_limits="Not specified in retrieved evidence.",
                    cost_sharing_or_deductible="Not specified in retrieved evidence.",
                    applicable_exclusions=[],
                ),
                cited_chunk_ids=[],
                self_grounding_score=0.0,
            )

        covered: set[str] = set()
        sentences: list[str] = []
        for ev in selected:
            best = max(
                (s.strip() for s in _SENTENCE_RE.split(ev.text) if s.strip()),
                key=lambda s: len(q_tokens & set(tokenize(s))),
                default="",
            )
            if best:
                sentences.append(f"{best} [{ev.evidence_id}]")
            covered |= q_tokens & set(tokenize(ev.text))
        grounding = round(len(covered) / len(q_tokens), 4)

        corpus = " ".join(ev.text for ev in selected)
        all_sentences = [s.strip() for s in _SENTENCE_RE.split(corpus) if s.strip()]

        def first(pattern: str) -> str:
            rx = re.compile(pattern, re.IGNORECASE)
            return next((s for s in all_sentences if rx.search(s)), "Not specified.")

        waiting = first(r"waiting")
        limits = next((s for s in all_sentences if _NUMERIC_RE.search(s)), "Not specified.")
        cost_share = first(r"co-?pay|deductible|proportionate")
        exclusions = find_excl_codes(corpus)
        query_l = request.user_query.lower()
        if re.search(r"exclu|not covered", query_l) and exclusions:
            status = "EXCLUDED"
        elif waiting != "Not specified." and re.search(r"wait|month|year|after", query_l):
            status = "WAITING_PERIOD_APPLIES"
        elif limits != "Not specified.":
            status = "COVERED_WITH_LIMITS"
        else:
            status = "COVERED"
        return LlmGroundedDraft(
            answer=" ".join(sentences),
            coverage_summary=PolicyCoverageSummary(
                coverage_status=status,
                waiting_period_details=waiting,
                applicable_sub_limits=limits,
                cost_sharing_or_deductible=cost_share,
                applicable_exclusions=exclusions,
            ),
            cited_chunk_ids=[ev.evidence_id for ev in selected],
            self_grounding_score=grounding,
        )

    # ------------------------------------------------------------------ embeddings
    def embed(self, texts: list[str], model: str, dim: int) -> EmbeddingResult:
        self.embed_calls += 1
        return EmbeddingResult(
            vectors=[hashing_embedding(t, dim) for t in texts],
            model=model,
            token_count=sum(_approx_tokens(t) for t in texts),
        )


def _bucket(feature: str, dim: int) -> tuple[int, float]:
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(digest, "big")
    return value % dim, (1.0 if (value >> 63) & 1 else -1.0)


def hashing_embedding(text: str, dim: int) -> list[float]:
    """Deterministic L2-normalised feature-hashing embedding (tokens + 5-char prefixes)."""
    vec = [0.0] * dim
    for tok in tokenize(text):
        idx, sign = _bucket(tok, dim)
        vec[idx] += sign
        if len(tok) > 5:
            idx, sign = _bucket(f"p:{tok[:5]}", dim)
            vec[idx] += 0.5 * sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]
