"""Grounded legal generation with calibrated confidence scoring and deterministic abstention (<0.70)."""

from __future__ import annotations

import uuid
from pathlib import Path

from insurance_mmrag.llm.gateway import ModelGateway
from insurance_mmrag.llm.protocol import EvidenceItem
from insurance_mmrag.schemas import (
    AssembledContext,
    GroundedCitation,
    GroundedQueryResponse,
    LlmGroundedDraft,
    PolicyCoverageSummary,
    QueryIntentClassification,
)
from insurance_mmrag.telemetry.trace_recorder import TraceRecorder

ABSTENTION_MESSAGE = (
    "INDETERMINATE COVERAGE (Confidence below 0.70 threshold): "
    "The indexed IRDAI policy document does not contain sufficient verifiable clauses "
    "to confirm coverage, sub-limits, or exclusions for this query. "
    "Please refer to the full Policy Schedule or contact the insurer's underwriting/claims desk."
)


class GroundedGenerator:
    """Synthesizes policy answers strictly grounded in retrieved parent/child evidence with citations."""

    def __init__(
        self,
        gateway: ModelGateway,
        flash_model: str = "gemini-2.5-flash",
        pro_model: str = "gemini-2.5-pro",
        min_confidence_threshold: float = 0.70,
    ) -> None:
        self.gateway = gateway
        self.flash_model = flash_model
        self.pro_model = pro_model
        self.min_confidence_threshold = min_confidence_threshold

    def generate_response(
        self,
        intent: QueryIntentClassification,
        context: AssembledContext,
        trace: TraceRecorder | None = None,
    ) -> GroundedQueryResponse:
        query_id = f"qry_{uuid.uuid4().hex[:10]}"
        model_name = self.pro_model if intent.requires_pro_escalation else self.flash_model

        if not context.retrieved:
            # Zero retrieval hits -> deterministic abstention
            return self._abstain_response(
                query_id=query_id,
                intent=intent,
                context=context,
                model_used=model_name,
                reason="No relevant policy clauses or schedules retrieved.",
                trace=trace,
            )

        # 1. Prepare evidence items for the LLM
        evidence_items: list[EvidenceItem] = []
        for r in context.retrieved:
            evidence_items.append(EvidenceItem(evidence_id=r.chunk.chunk_id, text=r.chunk.text))

        # Also supply full ParentChunks context preview
        for p in context.parents:
            parent_preview = f"--- [PARENT SECTION: {p.section_title} (Pages {p.start_page}-{p.end_page})] ---\n{p.full_text[:1200]}"
            evidence_items.append(EvidenceItem(evidence_id=p.parent_id, text=parent_preview))

        # 2. Collect image bytes for visual tables
        image_bytes: list[bytes] = []
        for r in context.retrieved:
            if r.chunk.metadata.image_crop_path:
                crop_p = Path(r.chunk.metadata.image_crop_path)
                if crop_p.exists():
                    image_bytes.append(crop_p.read_bytes())

        # 3. Model generation pass
        res = self.gateway.generate(
            task="grounded_answer",
            model=model_name,
            instruction=(
                "You are an expert Indian Insurance Policy Claims Assistant. "
                "Answer the user query strictly and solely using the provided policy evidence. "
                "Always cite exact page numbers, section types, and IRDAI exclusion codes (e.g. Excl01, Excl02) where applicable. "
                "If the evidence does not clearly confirm or exclude coverage, set coverage_status to INDETERMINATE. "
                "Do not guess or assume terms not stated in the evidence."
            ),
            schema=LlmGroundedDraft,
            operation="generation.grounded_answer",
            user_query=intent.redacted_query,
            evidence=tuple(evidence_items),
            images=tuple(image_bytes[:2]),  # Limit to 2 crops to optimize tokens
        )

        draft: LlmGroundedDraft = res.parsed

        # 4. Calibrate confidence score
        s_retrieval = context.retrieval_score
        s_llm = draft.self_grounding_score
        cited_cids = set(draft.cited_chunk_ids)
        retrieved_cids = {r.chunk.chunk_id for r in context.retrieved} | {
            p.parent_id for p in context.parents
        }
        valid_citations_count = len(cited_cids.intersection(retrieved_cids))
        s_citations = (
            min(1.0, valid_citations_count / max(1, len(cited_cids))) if cited_cids else 0.5
        )

        confidence = round(0.45 * s_retrieval + 0.35 * s_llm + 0.20 * s_citations, 4)

        # 5. Build citations
        citations = self._build_citations(draft.cited_chunk_ids, context)

        # 6. Check abstention threshold
        if (
            confidence < self.min_confidence_threshold
            or draft.coverage_summary.coverage_status == "INDETERMINATE"
        ):
            return self._abstain_response(
                query_id=query_id,
                intent=intent,
                context=context,
                model_used=model_name,
                reason=f"Confidence score {confidence:.2f} is below minimum {self.min_confidence_threshold:.2f}.",
                confidence=confidence,
                trace=trace,
            )

        spans = trace.spans() if trace else []

        return GroundedQueryResponse(
            query_id=query_id,
            answer=draft.answer,
            confidence_score=confidence,
            abstained=False,
            abstention_reason=None,
            coverage_summary=draft.coverage_summary,
            intent=intent,
            citations=citations,
            cross_referenced_parents=context.cross_referenced_parent_ids,
            crag_hops=context.crag_hops,
            precedence_check=context.precedence,
            pii_redactions_applied=res.pii_categories,
            injection_detected=res.injection_detected,
            model_used=model_name,
            trace_spans=spans,
            cost_telemetry=res.cost,
        )

    def _build_citations(
        self, cited_ids: list[str], context: AssembledContext
    ) -> list[GroundedCitation]:
        citations: list[GroundedCitation] = []
        retrieved_by_id = {r.chunk.chunk_id: r for r in context.retrieved}
        parents_by_id = {p.parent_id: p for p in context.parents}

        for idx, cid in enumerate(cited_ids):
            if cid in retrieved_by_id:
                r = retrieved_by_id[cid]
                chunk = r.chunk
                parent = parents_by_id.get(chunk.metadata.parent_id)
                citations.append(
                    GroundedCitation(
                        citation_id=f"cit_{idx + 1:02d}",
                        doc_id=chunk.metadata.doc_id,
                        policy_name=chunk.metadata.policy_name,
                        page_number=chunk.metadata.page_number,
                        section_type=chunk.metadata.section_type,
                        section_title=chunk.metadata.section_title,
                        clause_code=chunk.metadata.clause_code,
                        parent_id=chunk.metadata.parent_id,
                        child_chunk_id=chunk.chunk_id,
                        chunk_type=chunk.metadata.chunk_type,
                        verbatim_quote=chunk.text[:280],
                        parent_context_preview=(
                            parent.full_text[:400] if parent else "Context in policy schedule"
                        ),
                        image_crop_url=(
                            f"/api/v1/crops/{Path(chunk.metadata.image_crop_path).name}"
                            if chunk.metadata.image_crop_path
                            else None
                        ),
                        relevance_score=r.normalized_score,
                    )
                )

        # Fallback: if no valid cited IDs returned by draft, cite top retrieved chunks
        if not citations and context.retrieved:
            for idx, r in enumerate(context.retrieved[:3]):
                chunk = r.chunk
                parent = parents_by_id.get(chunk.metadata.parent_id)
                citations.append(
                    GroundedCitation(
                        citation_id=f"cit_{idx + 1:02d}",
                        doc_id=chunk.metadata.doc_id,
                        policy_name=chunk.metadata.policy_name,
                        page_number=chunk.metadata.page_number,
                        section_type=chunk.metadata.section_type,
                        section_title=chunk.metadata.section_title,
                        clause_code=chunk.metadata.clause_code,
                        parent_id=chunk.metadata.parent_id,
                        child_chunk_id=chunk.chunk_id,
                        chunk_type=chunk.metadata.chunk_type,
                        verbatim_quote=chunk.text[:280],
                        parent_context_preview=(
                            parent.full_text[:400] if parent else "Context in policy schedule"
                        ),
                        image_crop_url=(
                            f"/api/v1/crops/{Path(chunk.metadata.image_crop_path).name}"
                            if chunk.metadata.image_crop_path
                            else None
                        ),
                        relevance_score=r.normalized_score,
                    )
                )

        return citations

    def _abstain_response(
        self,
        query_id: str,
        intent: QueryIntentClassification,
        context: AssembledContext,
        model_used: str,
        reason: str,
        confidence: float = 0.35,
        trace: TraceRecorder | None = None,
    ) -> GroundedQueryResponse:
        cost = self.gateway.cost_tracker.record("generation.abstain", model_used, cache_hit=True)
        spans = trace.spans() if trace else []

        return GroundedQueryResponse(
            query_id=query_id,
            answer=ABSTENTION_MESSAGE,
            confidence_score=confidence,
            abstained=True,
            abstention_reason=reason,
            coverage_summary=PolicyCoverageSummary(
                coverage_status="INDETERMINATE",
                waiting_period_details="Not verifiable in available policy evidence.",
                applicable_sub_limits="Not verifiable in available policy evidence.",
                cost_sharing_or_deductible="Not verifiable in available policy evidence.",
                applicable_exclusions=[],
            ),
            intent=intent,
            citations=[],
            cross_referenced_parents=[],
            crag_hops=context.crag_hops,
            precedence_check=context.precedence,
            pii_redactions_applied=[],
            injection_detected=False,
            model_used=model_used,
            trace_spans=spans,
            cost_telemetry=cost,
        )
