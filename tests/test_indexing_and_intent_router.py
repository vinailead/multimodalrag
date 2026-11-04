"""Unit and integration tests for Multimodal Indexing, Hybrid Vector Store, and Intent Router (Modules 4 & 5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from insurance_mmrag.indexing.multimodal_embedder import MultimodalEmbedder
from insurance_mmrag.indexing.vector_store import HybridVectorStore
from insurance_mmrag.ingestion.parent_child_chunker import ParentChildChunker
from insurance_mmrag.ingestion.pdf_loader import PdfLoader
from insurance_mmrag.ingestion.sample_policy_factory import create_arogya_sanjeevani_pdf
from insurance_mmrag.ingestion.structure_analyzer import StructureAnalyzer
from insurance_mmrag.ingestion.table_vision_parser import TableVisionParser
from insurance_mmrag.llm.gateway import ModelGateway
from insurance_mmrag.retrieval.intent_router import IntentRouter
from insurance_mmrag.schemas import ChunkType, SectionType


@pytest.fixture
def embedder(gateway: ModelGateway) -> MultimodalEmbedder:
    return MultimodalEmbedder(gateway=gateway, dim=64)


@pytest.fixture
def vector_store() -> HybridVectorStore:
    return HybridVectorStore(location=":memory:", dim=64)


@pytest.fixture
def intent_router(gateway: ModelGateway) -> IntentRouter:
    return IntentRouter(gateway=gateway)


def test_multimodal_embedder_normalization(embedder: MultimodalEmbedder) -> None:
    vecs, _cost = embedder.embed_texts(["cataract waiting period", "room rent sub-limit"])
    assert len(vecs) == 2
    assert len(vecs[0]) == 64
    assert sum(v * v for v in vecs[0]) == pytest.approx(1.0, abs=1e-4)

    # Empty text list handles cleanly
    empty_vecs, _ = embedder.embed_texts([])
    assert empty_vecs == []

    # Single query embedding
    q_vec, _ = embedder.embed_query("AYUSH treatment cover")
    assert len(q_vec) == 64
    assert sum(v * v for v in q_vec) == pytest.approx(1.0, abs=1e-4)


def test_hybrid_vector_store_rrf_and_clause_boost(
    embedder: MultimodalEmbedder,
    vector_store: HybridVectorStore,
    gateway: ModelGateway,
    tmp_path: Path,
) -> None:
    pdf_path = create_arogya_sanjeevani_pdf(tmp_path / "arogya.pdf")
    loader = PdfLoader()
    _, pages = loader.load(pdf_path)

    analyzer = StructureAnalyzer(gateway)
    doc_struct = analyzer.analyze(pages, doc_id="arogya_sanjeevani")

    table_parser = TableVisionParser(
        gateway=gateway, crops_dir=tmp_path / "crops", cache_dir=tmp_path / "cache"
    )
    chunker = ParentChildChunker(table_parser=table_parser)
    ingested = chunker.chunk_document(doc_struct, pages)

    # Embed and index all child chunks
    texts = [c.text for c in ingested.children]
    vectors, _ = embedder.embed_texts(texts)
    indexed_count = vector_store.index_chunks(ingested.children, vectors)
    assert indexed_count == len(ingested.children)
    assert vector_store.count() == len(ingested.children)

    # Query 1: Exact clause code search for Excl01 (Pre-Existing Diseases)
    q1 = "What is waiting period code Excl01 for Pre-Existing Diseases?"
    q1_vec, _ = embedder.embed_query(q1)
    results1 = vector_store.hybrid_search(
        query=q1,
        query_vector=q1_vec,
        target_sections=[SectionType.WAITING_PERIODS, SectionType.EXCLUSIONS],
        detected_clause_codes=["Excl01"],
        top_k=3,
    )
    assert len(results1) > 0
    top_hit = results1[0]
    assert top_hit.chunk.metadata.section_type in (
        SectionType.WAITING_PERIODS,
        SectionType.EXCLUSIONS,
    )
    assert "Excl01" in (top_hit.chunk.metadata.clause_code or top_hit.chunk.text)
    assert top_hit.normalized_score >= 0.70

    # Query 2: Table boost for numerical room rent / cataract limits
    q2 = "What is the room rent limit and cataract sub-limit for 5 Lakh Sum Insured?"
    q2_vec, _ = embedder.embed_query(q2)
    results2 = vector_store.hybrid_search(
        query=q2,
        query_vector=q2_vec,
        target_sections=[SectionType.SCHEDULE_OF_BENEFITS, SectionType.COST_SHARING],
        boost_tables=True,
        top_k=4,
    )
    assert len(results2) > 0
    # Table chunks should be boosted to top
    has_table_chunk = any(r.chunk.metadata.chunk_type == ChunkType.TABLE for r in results2)
    assert has_table_chunk


def test_intent_router_classifies_and_decomposes(intent_router: IntentRouter) -> None:
    # 1. Simple waiting period query
    res1 = intent_router.classify_intent(
        "How long is the waiting period for cataract surgery under Code-Excl02?"
    )
    assert res1.primary_section in (SectionType.WAITING_PERIODS, SectionType.EXCLUSIONS)
    assert "Excl02" in res1.detected_clause_codes
    assert len(res1.sub_queries) == 1

    # 2. Table-heavy limit query
    res2 = intent_router.classify_intent(
        "What is the room rent limit and mandatory co-payment percentage?"
    )
    assert res2.requires_table_boost
    assert (
        SectionType.SCHEDULE_OF_BENEFITS in res2.target_sections
        or SectionType.COST_SHARING in res2.target_sections
    )

    # 3. Compound query decomposition for bounded CRAG
    compound = (
        "Is robotic surgery covered; what is the waiting period for pre-existing disease; "
        "and what is the room rent proportionate deduction?"
    )
    res3 = intent_router.classify_intent(compound)
    assert len(res3.sub_queries) >= 2
    assert res3.requires_pro_escalation

    # 4. PII masking in query
    pii_query = "My PAN is ABCDE1234F. What is the claim filing deadline?"
    res4 = intent_router.classify_intent(pii_query)
    assert "ABCDE1234F" not in res4.redacted_query
    assert "[REDACTED_PAN]" in res4.redacted_query
    assert res4.primary_section == SectionType.CLAIMS_AND_GRIEVANCE
