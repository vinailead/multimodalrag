"""Unit and integration tests for TableVisionParser (Module 3) and SHA-256 cache."""

from __future__ import annotations

from pathlib import Path

import pytest

from insurance_mmrag.ingestion.pdf_loader import PdfLoader
from insurance_mmrag.ingestion.sample_policy_factory import create_arogya_sanjeevani_pdf
from insurance_mmrag.ingestion.table_vision_parser import TableVisionParser
from insurance_mmrag.llm.gateway import ModelGateway
from insurance_mmrag.schemas import ChunkType, SectionType


@pytest.fixture
def table_parser(gateway: ModelGateway, tmp_path: Path) -> TableVisionParser:
    return TableVisionParser(
        gateway=gateway,
        crops_dir=tmp_path / "crops",
        cache_dir=tmp_path / "cache",
    )


def test_table_vision_parser_extracts_and_caches_benefit_table(
    table_parser: TableVisionParser, tmp_path: Path
) -> None:
    pdf_path = create_arogya_sanjeevani_pdf(tmp_path / "arogya.pdf")
    loader = PdfLoader()
    _, pages = loader.load(pdf_path)

    # Page 2 has the Schedule of Benefits table
    p2 = pages[1]
    assert len(p2.tables) >= 1
    region = p2.tables[0]

    # First run: vision extraction
    artifact = table_parser.parse_table(
        region=region,
        page=p2,
        doc_id="arogya_sanjeevani",
        section_type=SectionType.SCHEDULE_OF_BENEFITS,
        section_title="Schedule of Benefits",
        table_idx=1,
    )

    assert artifact.table_id == "tbl_arogya_sanjeevani_p2_1"
    assert artifact.page_number == 2
    assert artifact.section_type == SectionType.SCHEDULE_OF_BENEFITS
    assert Path(artifact.image_crop_path).exists()
    assert len(artifact.sha256_hash) == 64
    assert len(artifact.markdown_table) > 20
    assert len(artifact.structured_rows) >= 3
    assert len(artifact.synthetic_qa_pairs) >= 2

    # Second run: must hit SHA-256 disk cache with zero extra token cost
    cached_artifact = table_parser.parse_table(
        region=region,
        page=p2,
        doc_id="arogya_sanjeevani",
        section_type=SectionType.SCHEDULE_OF_BENEFITS,
        section_title="Schedule of Benefits",
        table_idx=1,
    )
    assert cached_artifact.sha256_hash == artifact.sha256_hash
    assert cached_artifact.title == artifact.title


def test_create_table_child_chunks(table_parser: TableVisionParser, tmp_path: Path) -> None:
    pdf_path = create_arogya_sanjeevani_pdf(tmp_path / "arogya.pdf")
    loader = PdfLoader()
    _, pages = loader.load(pdf_path)
    p2 = pages[1]
    artifact = table_parser.parse_table(
        region=p2.tables[0],
        page=p2,
        doc_id="arogya_sanjeevani",
        section_type=SectionType.SCHEDULE_OF_BENEFITS,
        section_title="Schedule of Benefits",
    )

    chunks = table_parser.create_table_child_chunks(
        artifact=artifact,
        parent_id="par_arogya_sec_02",
        policy_name="Arogya Sanjeevani",
        insurer_name="National Insurance",
        uin="NICHLIP20177V011920",
    )

    assert len(chunks) >= 3
    summary_chunk = chunks[0]
    assert summary_chunk.metadata.chunk_type == ChunkType.TABLE
    assert summary_chunk.metadata.parent_id == "par_arogya_sec_02"
    assert "TABLE:" in summary_chunk.text

    # Synthetic Q&A chunks
    qa_chunks = chunks[1:]
    for qac in qa_chunks:
        assert qac.metadata.chunk_type == ChunkType.TABLE
        assert qac.metadata.parent_id == "par_arogya_sec_02"
        assert qac.text.startswith("Q: What is the")
