"""Unit and integration tests for GroundedGenerator, Confidence Scoring, and Abstention (Module 6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from insurance_mmrag.generation.grounded_generator import ABSTENTION_MESSAGE
from insurance_mmrag.ingestion.sample_policy_factory import create_arogya_sanjeevani_pdf
from insurance_mmrag.llm.gateway import ModelGateway
from insurance_mmrag.pipeline import InsuranceMMRAGPipeline
from insurance_mmrag.schemas import GroundedQueryResponse


@pytest.fixture
def pipeline(gateway: ModelGateway, tmp_path: Path) -> InsuranceMMRAGPipeline:
    from insurance_mmrag.config import Settings
    from insurance_mmrag.indexing.vector_store import HybridVectorStore

    settings = Settings(
        data_dir=tmp_path / "data",
        logs_dir=tmp_path / "logs",
        use_stub_model=True,
    )
    store = HybridVectorStore(dim=768)
    pipe = InsuranceMMRAGPipeline(gateway=gateway, settings=settings, vector_store=store)

    pdf_path = create_arogya_sanjeevani_pdf(tmp_path / "arogya.pdf")
    pipe.ingest_pdf(pdf_path, doc_id="arogya_sanjeevani")
    return pipe


def test_grounded_generation_supported_query(pipeline: InsuranceMMRAGPipeline) -> None:
    query = "What is the waiting period for cataract surgery under this policy?"
    resp: GroundedQueryResponse = pipeline.query(query)

    assert not resp.abstained
    assert resp.confidence_score >= 0.70
    assert resp.coverage_summary.coverage_status in (
        "WAITING_PERIOD_APPLIES",
        "COVERED_WITH_LIMITS",
    )
    assert len(resp.citations) >= 1

    top_cit = resp.citations[0]
    assert top_cit.page_number >= 1
    assert len(top_cit.verbatim_quote) > 10
    assert top_cit.parent_id.startswith("par_arogya_sanjeevani_")

    # Trace waterfall spans recorded
    assert len(resp.trace_spans) >= 3
    span_names = [s.name for s in resp.trace_spans]
    assert "retrieval.intent_route" in span_names
    assert "retrieval.context_assembly" in span_names
    assert "generation.grounded_synthesis" in span_names


def test_grounded_generation_adversarial_abstention(pipeline: InsuranceMMRAGPipeline) -> None:
    # Query completely outside policy scope
    query = "Does this policy cover pet veterinary dental implants in Antarctica?"
    resp: GroundedQueryResponse = pipeline.query(query)

    assert resp.abstained
    assert resp.confidence_score < 0.70
    assert resp.coverage_summary.coverage_status == "INDETERMINATE"
    assert ABSTENTION_MESSAGE in resp.answer
    assert resp.abstention_reason is not None
    assert len(resp.citations) == 0


def test_grounded_generation_with_pro_escalation(pipeline: InsuranceMMRAGPipeline) -> None:
    compound_query = (
        "Is robotic surgery covered; what is the waiting period for pre-existing disease (Excl01); "
        "and what is the room rent proportionate deduction?"
    )
    resp: GroundedQueryResponse = pipeline.query(compound_query)

    assert resp.intent.requires_pro_escalation
    assert resp.model_used == pipeline.settings.pro_model
    assert len(resp.crag_hops) >= 1
