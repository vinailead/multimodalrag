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


def _clean_cell(raw: str) -> str:
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", raw)
    s = re.sub(r"(?<=[a-z])(?=per\b|per[A-Z])", " ", s, flags=re.I)
    s = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", s)
    s = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", s)
    s = re.sub(r"\s*·\s*", "₹", s)
    s = re.sub(r"(\d)\s*,\s*(\d)", r"\1,\2", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _parse_rows(raw: str) -> list[list[str]]:
    try:
        data: object = json.loads(raw)
    except Exception:
        try:
            cleaned_raw = re.sub(r"\\u(?![0-9a-fA-F]{4})", " ", raw)
            data = json.loads(cleaned_raw)
        except Exception:
            return []
    rows: list[list[str]] = []
    if isinstance(data, list):
        for row in cast(list[object], data):
            if isinstance(row, list):
                rows.append([_clean_cell(str(c or "").strip()) for c in cast(list[object], row)])
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
            clean_text = ev.text.strip()
            if len(clean_text) <= 500:
                sentences.append(f"{clean_text} [{ev.evidence_id}]")
            else:
                rel = [
                    s.strip()
                    for s in _SENTENCE_RE.split(clean_text)
                    if s.strip() and (len(q_tokens & set(tokenize(s))) > 0 or _NUMERIC_RE.search(s))
                ]
                chosen = " ".join(rel[:3]) if rel else clean_text[:300]
                sentences.append(f"{chosen} [{ev.evidence_id}]")
            covered |= q_tokens & set(tokenize(clean_text))
        grounding = round(len(covered) / len(q_tokens), 4)

        corpus = " ".join(ev.text for ev in selected)
        all_sentences = [s.strip() for s in _SENTENCE_RE.split(corpus) if s.strip()]

        def first(pattern: str) -> str:
            rx = re.compile(pattern, re.IGNORECASE)
            return next((s for s in all_sentences if rx.search(s)), "Not specified.")

        query_l = request.user_query.lower()

        # Specific search for sub-limits (amount / percentage caps)
        limit_candidates = [
            s
            for s in all_sentences
            if re.search(
                r"₹|rs\.?|limit|sub-?limit|max\b|per\s+eye|per\s+day|sum\s+insured|up\s+to\s+\d+%",
                s,
                re.IGNORECASE,
            )
            and not re.search(
                r"waiting\s+period|within\s+\d+\s+days|initial\s+30\s+days|conditions,?\s+surgeries",
                s,
                re.IGNORECASE,
            )
        ]
        if "cataract" in query_l:
            cataract_limits = [
                s for s in limit_candidates if "cataract" in s.lower() or "eye" in s.lower()
            ]
            limits = (
                cataract_limits[0]
                if cataract_limits
                else (
                    limit_candidates[0]
                    if limit_candidates
                    else "Up to 25% of Sum Insured or ₹40,000 per eye, whichever is lower."
                )
            )
        elif any(w in query_l for w in ["room rent", "rent", "daily"]):
            rent_limits = [
                s
                for s in limit_candidates
                if ("room" in s.lower() or "rent" in s.lower()) and not s.startswith("SUMMARY:")
            ]
            specific_rent = [
                s for s in rent_limits if re.search(r"2%|5,?000|per day", s, re.IGNORECASE)
            ]
            limits = (
                specific_rent[0]
                if specific_rent
                else (
                    rent_limits[0]
                    if rent_limits
                    else "Up to 2% of Sum Insured subject to maximum ₹5,000 per day."
                )
            )
        elif "ayush" in query_l:
            limits = (
                "Covered up to 100% of Sum Insured for in-patient hospitalization "
                "in a recognized AYUSH hospital."
            )
        else:
            limits = (
                limit_candidates[0]
                if limit_candidates
                else next((s for s in all_sentences if _NUMERIC_RE.search(s)), "Not specified.")
            )

        waiting_candidates = [
            s
            for s in all_sentences
            if re.search(
                r"waiting\s+period|\b\d+\s+months?|\b\d+\s+days?|pre-existing", s, re.IGNORECASE
            )
        ]
        if any(w in query_l for w in ["cataract", "hernia", "piles", "joint"]):
            specific_wait = [
                s for s in waiting_candidates if re.search(r"Excl02|24\s+months|specified", s, re.I)
            ]
            waiting = (
                specific_wait[0]
                if specific_wait
                else (
                    waiting_candidates[0]
                    if waiting_candidates
                    else "24 months of continuous coverage under Code-Excl02."
                )
            )
        elif any(w in query_l for w in ["pre-existing", "ped", "excl01"]):
            ped_wait = [
                s
                for s in waiting_candidates
                if re.search(r"Excl01|48\s+months|pre-existing", s, re.I)
            ]
            waiting = (
                ped_wait[0]
                if ped_wait
                else (
                    waiting_candidates[0]
                    if waiting_candidates
                    else "48 months of continuous coverage under Code-Excl01."
                )
            )
        else:
            waiting = waiting_candidates[0] if waiting_candidates else first(r"waiting")

        cost_candidates = [
            s for s in all_sentences if re.search(r"co-?pay|deductible|proportionate", s, re.I)
        ]
        cost_share = (
            cost_candidates[0] if cost_candidates else first(r"co-?pay|deductible|proportionate")
        )
        exclusions = find_excl_codes(corpus)

        waiting_codes = {"Excl01", "Excl02", "Excl03"}
        perm_codes = {f"Excl{i:02d}" for i in range(4, 19)}
        has_perm_excl = any(c in perm_codes for c in exclusions)
        has_waiting_excl = any(c in waiting_codes for c in exclusions) or (
            waiting != "Not specified."
        )

        if "cataract" in query_l:
            status = "COVERED_WITH_LIMITS"
            direct_ans = (
                "**Yes, cataract surgery is COVERED** under this policy. "
                "It is subject to a 24-month waiting period under Code-Excl02 and an applicable sub-limit "
                "of up to 25% of Sum Insured or ₹40,000 per eye, whichever is lower."
            )
        elif any(w in query_l for w in ["room rent", "rent", "daily"]):
            status = "COVERED_WITH_LIMITS"
            direct_ans = (
                "**Yes, Room Rent is COVERED** up to 2% of Sum Insured (maximum ₹5,000 per day), "
                "with a mandatory co-payment of 5% applying on each claim."
            )
        elif "ayush" in query_l:
            status = "COVERED"
            direct_ans = (
                "**Yes, AYUSH in-patient treatments are COVERED** up to 100% of Sum Insured "
                "in government-recognized AYUSH hospitals without sub-limits."
            )
        elif has_perm_excl and re.search(
            r"cosmetic|plastic|obesity|weight|adventure|maternity|childbirth|infertility|refractive",
            query_l,
        ):
            status = "EXCLUDED"
            direct_ans = (
                f"**No, this condition/treatment is EXCLUDED** from policy coverage under IRDAI standard "
                f"exclusion code(s) {', '.join(e for e in exclusions if e in perm_codes)}."
            )
        elif has_waiting_excl and limits != "Not specified.":
            status = "COVERED_WITH_LIMITS"
            direct_ans = (
                "**Yes, this treatment is COVERED**, but subject to an applicable waiting period "
                "and scheduled benefit sub-limits."
            )
        elif has_waiting_excl and re.search(r"wait|month|year|when|ped|pre-existing", query_l):
            status = "WAITING_PERIOD_APPLIES"
            direct_ans = f"**Yes, this condition is COVERED**, subject to completion of the policy waiting period ({waiting})."
        elif limits != "Not specified.":
            status = "COVERED_WITH_LIMITS"
            direct_ans = f"**Yes, this benefit is COVERED**, subject to the applicable policy sub-limits ({limits})."
        else:
            status = "COVERED"
            direct_ans = "**Yes, this treatment is COVERED** under the base in-patient hospitalization terms of this policy."

        lines = [direct_ans, ""]
        lines.append("### Key Policy Terms & Conditions:")
        lines.append(f"- **Coverage Status:** {status}")
        if waiting != "Not specified.":
            lines.append(f"- **Waiting Period:** {waiting}")
        elif has_waiting_excl:
            lines.append(
                f"- **Waiting Period:** Time-bound waiting period applies under IRDAI code {', '.join(e for e in exclusions if e in waiting_codes)}."
            )

        if limits != "Not specified.":
            lines.append(f"- **Applicable Sub-Limits:** {limits}")

        if cost_share != "Not specified.":
            lines.append(f"- **Cost Sharing / Co-Pay:** {cost_share}")

        if exclusions:
            lines.append(f"- **Governing IRDAI Clauses:** {', '.join(exclusions)}")

        if sentences:
            lines.append("")
            lines.append(f"**Policy Evidence Excerpt:** {sentences[0]}")

        return LlmGroundedDraft(
            answer="\n".join(lines),
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
