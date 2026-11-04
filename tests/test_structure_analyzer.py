"""Unit and integration tests for PDF layout loading and Pre-Chunking Structure Analyzer (Module 1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from insurance_mmrag.ingestion.pdf_loader import PdfLoader
from insurance_mmrag.ingestion.sample_policy_factory import (
    create_arogya_sanjeevani_pdf,
    create_saral_suraksha_bima_pdf,
)
from insurance_mmrag.ingestion.structure_analyzer import StructureAnalyzer
from insurance_mmrag.llm.gateway import ModelGateway
from insurance_mmrag.schemas import SectionType


@pytest.fixture
def arogya_pdf_path(tmp_path: Path) -> Path:
    return create_arogya_sanjeevani_pdf(tmp_path / "arogya_sanjeevani.pdf")


@pytest.fixture
def saral_pdf_path(tmp_path: Path) -> Path:
    return create_saral_suraksha_bima_pdf(tmp_path / "saral_suraksha.pdf")


def test_pdf_loader_extracts_pages_blocks_and_tables(arogya_pdf_path: Path) -> None:
    loader = PdfLoader()
    doc, pages = loader.load(arogya_pdf_path)
    assert len(pages) == 6
    assert doc.page_count == 6

    # Verify text blocks on page 1
    p1 = pages[0]
    assert p1.page_number == 1
    assert "AROGYA SANJEEVANI POLICY" in p1.raw_text
    assert "NICHLIP20177V011920" in p1.raw_text
    assert len(p1.blocks) > 0

    # Verify table extracted on page 2 (Schedule of Benefits)
    p2 = pages[1]
    assert p2.page_number == 2
    assert len(p2.tables) >= 1
    tbl = p2.tables[0]
    assert tbl.page_number == 2
    assert len(tbl.bbox) == 4

    # Verify high-DPI rendering
    png_bytes = p2.render_png(dpi=150)
    assert png_bytes.startswith(b"\x89PNG")
    assert len(png_bytes) > 1000

    crop_path = arogya_pdf_path.parent / "test_crop.png"
    p2.save_crop(crop_path, tbl.bbox, dpi=150)
    assert crop_path.exists()
    assert crop_path.stat().st_size > 500


def test_structure_analyzer_identifies_all_9_irdai_sections(
    arogya_pdf_path: Path, gateway: ModelGateway
) -> None:
    loader = PdfLoader()
    _, pages = loader.load(arogya_pdf_path)

    analyzer = StructureAnalyzer(gateway)
    doc_struct = analyzer.analyze(pages, doc_id="arogya_sanjeevani_national")

    assert doc_struct.doc_id == "arogya_sanjeevani_national"
    assert "National Insurance" in doc_struct.insurer_name
    assert doc_struct.uin == "NICHLIP20177V011920"
    assert doc_struct.page_count == 6

    detected_types = [s.section_type for s in doc_struct.sections]

    # Verify canonical IRDAI sections were detected
    assert SectionType.CIS_SUMMARY in detected_types
    assert SectionType.SCHEDULE_OF_BENEFITS in detected_types
    assert SectionType.DEFINITIONS in detected_types
    assert SectionType.BASE_COVERAGE in detected_types
    assert SectionType.OPTIONAL_RIDERS in detected_types
    assert SectionType.WAITING_PERIODS in detected_types
    assert SectionType.EXCLUSIONS in detected_types
    assert SectionType.COST_SHARING in detected_types
    assert SectionType.CLAIMS_AND_GRIEVANCE in detected_types

    # Verify Schedule of Benefits has the table attached
    sched_sec = next(
        s for s in doc_struct.sections if s.section_type == SectionType.SCHEDULE_OF_BENEFITS
    )
    assert len(sched_sec.tables) >= 1
    assert sched_sec.start_page == 2

    # Verify Waiting Periods section has Excl01/Excl02 clauses
    wait_sec = next(s for s in doc_struct.sections if s.section_type == SectionType.WAITING_PERIODS)
    assert "Excl01" in wait_sec.text
    assert "Excl02" in wait_sec.text


def test_structure_analyzer_handles_saral_suraksha(
    saral_pdf_path: Path, gateway: ModelGateway
) -> None:
    loader = PdfLoader()
    _, pages = loader.load(saral_pdf_path)

    analyzer = StructureAnalyzer(gateway)
    doc_struct = analyzer.analyze(pages, doc_id="saral_suraksha_hdfc_ergo")

    assert doc_struct.uin == "HDFPAIP21175V012021"
    assert "HDFC ERGO" in doc_struct.insurer_name.upper()
    assert doc_struct.page_count == 3

    types = [s.section_type for s in doc_struct.sections]
    assert SectionType.CIS_SUMMARY in types
    assert SectionType.BASE_COVERAGE in types
    assert SectionType.EXCLUSIONS in types
    assert SectionType.CLAIMS_AND_GRIEVANCE in types
