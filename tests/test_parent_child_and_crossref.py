"""Unit and integration tests for Parent-Child Chunker and Cross-Reference Resolver (Module 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from insurance_mmrag.ingestion.cross_ref_resolver import CrossReferenceResolver
from insurance_mmrag.ingestion.parent_child_chunker import ParentChildChunker
from insurance_mmrag.ingestion.pdf_loader import PdfLoader
from insurance_mmrag.ingestion.sample_policy_factory import create_arogya_sanjeevani_pdf
from insurance_mmrag.ingestion.structure_analyzer import StructureAnalyzer
from insurance_mmrag.ingestion.table_vision_parser import TableVisionParser
from insurance_mmrag.llm.gateway import ModelGateway
from insurance_mmrag.schemas import ChunkType, ParentChunk, SectionType


@pytest.fixture
def cross_ref_resolver() -> CrossReferenceResolver:
    return CrossReferenceResolver()


def test_cross_ref_resolver_extracts_codes(cross_ref_resolver: CrossReferenceResolver) -> None:
    text = (
        "Subject to Waiting Periods under Code-Excl01 (Pre-Existing Diseases) and Code-Excl02. "
        "Also see Section 3.1(a) for Room Rent sub-limit and Def. 22 for AYUSH hospital definition."
    )
    codes = cross_ref_resolver.extract_clause_codes(text)
    assert "Excl01" in codes
    assert "Excl02" in codes
    assert "Section_3.1(a)" in codes
    assert "Def_22" in codes


def test_cross_ref_resolver_links_defined_terms_and_precedence(
    cross_ref_resolver: CrossReferenceResolver,
) -> None:
    p_defs = ParentChunk(
        parent_id="par_defs",
        doc_id="doc1",
        section_type=SectionType.DEFINITIONS,
        section_title="Definitions",
        start_page=3,
        end_page=3,
        full_text="2.9 Pre-Existing Disease (PED): defined here. 2.2 AYUSH Hospital: defined here.",
        markdown_tables=[],
        image_crop_paths=[],
        clause_codes=["Clause_2.9", "Clause_2.2"],
        cross_references=[],
    )
    p_cis = ParentChunk(
        parent_id="par_cis",
        doc_id="doc1",
        section_type=SectionType.CIS_SUMMARY,
        section_title="CIS",
        start_page=1,
        end_page=1,
        full_text="Summary of Pre-Existing Disease coverage and AYUSH treatment.",
        markdown_tables=[],
        image_crop_paths=[],
        clause_codes=[],
        cross_references=[],
    )
    p_wait = ParentChunk(
        parent_id="par_wait",
        doc_id="doc1",
        section_type=SectionType.WAITING_PERIODS,
        section_title="Waiting Periods",
        start_page=5,
        end_page=5,
        full_text="Excl01: 48 months waiting period for Pre-Existing Diseases.",
        markdown_tables=[],
        image_crop_paths=[],
        clause_codes=["Excl01"],
        cross_references=[],
    )
    parent_index = {"par_defs": p_defs, "par_cis": p_cis, "par_wait": p_wait}

    # Resolve references
    linked = cross_ref_resolver.resolve_references(p_cis.full_text, parent_index)
    assert "par_defs" in linked

    # Check precedence when CIS is cited
    prec_cis = cross_ref_resolver.check_precedence(["par_cis"], parent_index)
    assert prec_cis.cis_cited
    assert prec_cis.nuance_flag
    assert "par_wait" in prec_cis.binding_parent_ids
    assert "IRDAI Precedence Rule" in prec_cis.rule_applied

    # Check precedence when direct policy wording is cited
    prec_direct = cross_ref_resolver.check_precedence(["par_wait"], parent_index)
    assert not prec_direct.cis_cited
    assert not prec_direct.nuance_flag


def test_parent_child_chunker_end_to_end(gateway: ModelGateway, tmp_path: Path) -> None:
    pdf_path = create_arogya_sanjeevani_pdf(tmp_path / "arogya.pdf")
    loader = PdfLoader()
    _, pages = loader.load(pdf_path)

    analyzer = StructureAnalyzer(gateway)
    doc_struct = analyzer.analyze(pages, doc_id="arogya_sanjeevani_national")

    table_parser = TableVisionParser(
        gateway=gateway,
        crops_dir=tmp_path / "crops",
        cache_dir=tmp_path / "cache",
    )
    chunker = ParentChildChunker(table_parser=table_parser)
    ingested = chunker.chunk_document(doc_struct, pages)

    # Verify Parents
    assert len(ingested.parents) >= 7
    parent_ids = {p.parent_id for p in ingested.parents}

    # Verify Children
    assert len(ingested.children) >= 15
    for child in ingested.children:
        # Every child MUST point to a valid parent
        assert child.metadata.parent_id in parent_ids
        assert child.metadata.doc_id == "arogya_sanjeevani_national"
        assert len(child.metadata.sha256_hash) == 64
        assert child.metadata.page_number >= 1

    # Verify table child chunks exist
    table_children = [c for c in ingested.children if c.metadata.chunk_type == ChunkType.TABLE]
    assert len(table_children) >= 3

    # Verify cross-reference linking between coverage clause and definition parent
    wait_children = [
        c
        for c in ingested.children
        if c.metadata.section_type == SectionType.WAITING_PERIODS
        and "Excl01" in (c.metadata.clause_code or "")
    ]
    assert len(wait_children) >= 1
    defs_parent = next(
        (p for p in ingested.parents if p.section_type == SectionType.DEFINITIONS), None
    )
    assert defs_parent is not None
    # Waiting period clause for PED should link to Definitions parent
    assert defs_parent.parent_id in wait_children[0].metadata.cross_references
