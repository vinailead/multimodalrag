"""Pre-chunking structure analyzer mapping PDF layout to IRDAI functional taxonomy."""

from __future__ import annotations

import re

from insurance_mmrag.domain.irdai import classify_heading
from insurance_mmrag.ingestion.pdf_loader import LoadedPdfPage
from insurance_mmrag.llm.gateway import ModelGateway
from insurance_mmrag.schemas import (
    DetectedSection,
    DocumentStructure,
    SectionClassificationDraft,
    SectionType,
    TableRegion,
    TextBlock,
)

UIN_PATTERN = re.compile(r"\b(?:IRDAI\s+UIN|UIN)\s*[:\-]?\s*([A-Z0-9]{10,24})\b", re.IGNORECASE)
INSURER_PATTERN = re.compile(
    r"(National\s+Insurance|HDFC\s+ERGO|Star\s+Health|ICICI\s+Lombard|Care\s+Health|Niva\s+Bupa|Bajaj\s+Allianz|New\s+India\s+Assurance|Oriental\s+Insurance|United\s+India\s+Insurance)",
    re.IGNORECASE,
)


class StructureAnalyzer:
    """Analyzes whole document architecture and partitions it into canonical IRDAI sections."""

    def __init__(self, gateway: ModelGateway, model: str = "gemini-2.5-flash") -> None:
        self.gateway = gateway
        self.model = model

    def analyze(self, pages: list[LoadedPdfPage], doc_id: str) -> DocumentStructure:
        policy_name, insurer_name, uin = self._extract_metadata(pages, doc_id)
        sections = self._partition_sections(pages)

        return DocumentStructure(
            doc_id=doc_id,
            policy_name=policy_name,
            insurer_name=insurer_name,
            uin=uin,
            page_count=len(pages),
            sections=sections,
        )

    def _extract_metadata(
        self, pages: list[LoadedPdfPage], default_id: str
    ) -> tuple[str, str, str]:
        first_pages_text = "\n".join(p.raw_text for p in pages[:2])

        uin = "IRDAI_STANDARD_POLICY"
        uin_match = UIN_PATTERN.search(first_pages_text)
        if uin_match:
            uin = uin_match.group(1).strip()

        insurer = "Standard Indian Insurer"
        ins_match = INSURER_PATTERN.search(first_pages_text)
        if ins_match:
            insurer = ins_match.group(1).strip().title()

        lines = [ln.strip() for ln in pages[0].raw_text.splitlines() if ln.strip()]
        policy_name = lines[0] if lines else default_id.replace("_", " ").title()

        return policy_name, insurer, uin

    def _partition_sections(self, pages: list[LoadedPdfPage]) -> list[DetectedSection]:
        # Identify section boundaries by scanning text blocks
        boundaries: list[tuple[int, SectionType, str, list[TextBlock], list[TableRegion]]] = []
        current_type: SectionType | None = None
        current_title: str = ""
        current_blocks: list[TextBlock] = []
        current_start_page: int = 1

        for page in pages:
            for block in page.blocks:
                is_candidate_heading = (block.font_size >= 9.5 and block.is_bold) or (
                    re.match(r"^(?:SECTION|CUSTOMER|PART)\s+\d*|CIS", block.text, re.IGNORECASE)
                    is not None
                )
                detected_type: SectionType | None = None

                if is_candidate_heading:
                    detected_type = classify_heading(block.text)
                    if detected_type is None and len(block.text.splitlines()) <= 3:
                        # Ambiguous heading -> call classification gate
                        res = self.gateway.generate(
                            task="structure_classify",
                            model=self.model,
                            instruction="Classify the insurance policy heading into one of the 9 IRDAI section types.",
                            schema=SectionClassificationDraft,
                            operation="ingest.classify_heading",
                            hints={"heading": block.text, "preview": block.text[:200]},
                        )
                        if res.parsed.confidence >= 0.70:
                            detected_type = res.parsed.section_type

                if detected_type is not None:
                    # New section starts
                    if current_type is not None and current_blocks:
                        boundaries.append(
                            (current_start_page, current_type, current_title, current_blocks, [])
                        )
                    current_type = detected_type
                    current_title = block.text.splitlines()[0][:80]
                    current_start_page = page.page_number
                    current_blocks = [block]
                else:
                    if current_type is None:
                        # Before first explicit heading, default based on content or CIS
                        current_type = classify_heading(block.text) or SectionType.CIS_SUMMARY
                        current_title = block.text.splitlines()[0][:80]
                        current_start_page = page.page_number
                    current_blocks.append(block)

        if current_type is not None and current_blocks:
            boundaries.append((current_start_page, current_type, current_title, current_blocks, []))

        # Assign table regions to sections
        all_tables = [(p.page_number, t) for p in pages for t in p.tables]
        sections: list[DetectedSection] = []

        for idx, (start_p, s_type, title, blocks, _) in enumerate(boundaries):
            end_p = pages[-1].page_number if idx == len(boundaries) - 1 else boundaries[idx + 1][0]
            if end_p < start_p:
                end_p = start_p

            section_tables = [t for p_num, t in all_tables if start_p <= p_num <= end_p]
            section_text = "\n\n".join(b.text for b in blocks)

            sections.append(
                DetectedSection(
                    section_id=f"sec_{idx + 1:02d}_{s_type.value.lower()}",
                    section_type=s_type,
                    title=title,
                    start_page=start_p,
                    end_page=end_p,
                    text=section_text,
                    tables=section_tables,
                )
            )

        return sections
