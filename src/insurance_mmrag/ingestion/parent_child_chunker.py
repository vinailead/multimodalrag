"""Parent-child hierarchical chunker with cross-reference graph and vision table integration."""

from __future__ import annotations

import hashlib
import re

from insurance_mmrag.domain.irdai import tokenize
from insurance_mmrag.ingestion.cross_ref_resolver import CrossReferenceResolver
from insurance_mmrag.ingestion.pdf_loader import LoadedPdfPage
from insurance_mmrag.ingestion.table_vision_parser import TableVisionParser
from insurance_mmrag.schemas import (
    ChildChunk,
    ChunkMetadata,
    ChunkType,
    DetectedSection,
    DocumentStructure,
    ExtractedTableArtifact,
    IngestedDocument,
    ParentChunk,
)

PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n|(?<=\.\s)\n(?=[A-Z0-9])")


class ParentChildChunker:
    """Chunks documents into a dual hierarchy: full ParentChunks + atomic ChildChunks."""

    def __init__(
        self,
        table_parser: TableVisionParser,
        cross_ref_resolver: CrossReferenceResolver | None = None,
    ) -> None:
        self.table_parser = table_parser
        self.cross_ref_resolver = cross_ref_resolver or CrossReferenceResolver()

    def chunk_document(
        self,
        structure: DocumentStructure,
        pages: list[LoadedPdfPage],
    ) -> IngestedDocument:
        page_map = {p.page_number: p for p in pages}
        all_parents: list[ParentChunk] = []
        all_children: list[ChildChunk] = []
        all_tables: list[ExtractedTableArtifact] = []
        section_tables_map: dict[str, list[ExtractedTableArtifact]] = {}

        # First pass: parse tables and create ParentChunks
        for sec in structure.sections:
            sec_tables: list[ExtractedTableArtifact] = []
            for t_idx, region in enumerate(sec.tables):
                page = page_map.get(region.page_number)
                if page:
                    art = self.table_parser.parse_table(
                        region=region,
                        page=page,
                        doc_id=structure.doc_id,
                        section_type=sec.section_type,
                        section_title=sec.title,
                        table_idx=t_idx + 1,
                    )
                    sec_tables.append(art)
                    all_tables.append(art)

            section_tables_map[sec.section_id] = sec_tables

            md_tables = [t.markdown_table for t in sec_tables]
            crops = [t.image_crop_path for t in sec_tables]
            clause_codes = self.cross_ref_resolver.extract_clause_codes(sec.text)

            parent_id = f"par_{structure.doc_id}_{sec.section_id}"
            parent = ParentChunk(
                parent_id=parent_id,
                doc_id=structure.doc_id,
                section_type=sec.section_type,
                section_title=sec.title,
                start_page=sec.start_page,
                end_page=sec.end_page,
                full_text=sec.text,
                markdown_tables=md_tables,
                image_crop_paths=crops,
                clause_codes=clause_codes,
                cross_references=[],
            )
            all_parents.append(parent)

        # Build parent index for cross-reference linking
        parent_index = {p.parent_id: p for p in all_parents}

        # Second pass: resolve cross-references and generate ChildChunks
        for parent, sec in zip(all_parents, structure.sections, strict=True):
            # Resolve parent-level cross-references
            parent.cross_references = self.cross_ref_resolver.resolve_references(
                parent.full_text, parent_index
            )

            # Generate textual child chunks
            child_paragraphs = self._split_section_into_child_blocks(sec)
            for c_idx, (p_num, clause_code, text) in enumerate(child_paragraphs):
                # Resolve cross-references for this child
                child_refs = self.cross_ref_resolver.resolve_references(text, parent_index)
                sha_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

                meta = ChunkMetadata(
                    doc_id=structure.doc_id,
                    policy_name=structure.policy_name,
                    insurer_name=structure.insurer_name,
                    uin=structure.uin,
                    section_type=sec.section_type,
                    section_title=sec.title,
                    page_number=p_num,
                    chunk_type=ChunkType.TEXT,
                    parent_id=parent.parent_id,
                    clause_code=clause_code,
                    cross_references=child_refs,
                    image_crop_path=parent.image_crop_paths[0] if parent.image_crop_paths else None,
                    sha256_hash=sha_hash,
                )
                chunk_id = f"chk_{structure.doc_id}_{sec.section_id}_{c_idx + 1:02d}"
                all_children.append(
                    ChildChunk(
                        chunk_id=chunk_id,
                        text=text,
                        embedding_input=text,
                        metadata=meta,
                    )
                )

            # Add table child chunks
            sec_table_artifacts = section_tables_map.get(sec.section_id, [])
            for art in sec_table_artifacts:
                table_children = self.table_parser.create_table_child_chunks(
                    artifact=art,
                    parent_id=parent.parent_id,
                    policy_name=structure.policy_name,
                    insurer_name=structure.insurer_name,
                    uin=structure.uin,
                )
                all_children.extend(table_children)

        return IngestedDocument(
            structure=structure,
            parents=all_parents,
            children=all_children,
            tables=all_tables,
        )

    def _split_section_into_child_blocks(
        self, sec: DetectedSection
    ) -> list[tuple[int, str | None, str]]:
        """Split a section into atomic clauses/paragraphs with estimated page numbers."""
        blocks: list[tuple[int, str | None, str]] = []
        raw_paragraphs = [p.strip() for p in PARAGRAPH_SPLIT_RE.split(sec.text) if p.strip()]

        total_p = max(1, sec.end_page - sec.start_page + 1)
        for idx, para in enumerate(raw_paragraphs):
            # Estimate page number across the section's range
            page_offset = int((idx / max(1, len(raw_paragraphs))) * total_p)
            p_num = min(sec.end_page, sec.start_page + page_offset)

            # Extract any prominent clause code at the start
            codes = self.cross_ref_resolver.extract_clause_codes(para[:120])
            clause_code = codes[0] if codes else None

            # Only retain blocks with enough informational content
            if len(tokenize(para)) >= 4:
                blocks.append((p_num, clause_code, para))

        return blocks
