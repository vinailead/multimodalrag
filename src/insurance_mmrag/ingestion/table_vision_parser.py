"""Gemini 2.5 Vision table extraction, context enrichment, and synthetic Q&A generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from insurance_mmrag.ingestion.pdf_loader import LoadedPdfPage
from insurance_mmrag.llm.gateway import ModelGateway
from insurance_mmrag.schemas import (
    ChildChunk,
    ChunkMetadata,
    ChunkType,
    ExtractedTableArtifact,
    SectionType,
    TableExtractionDraft,
    TableRegion,
)
from insurance_mmrag.telemetry.cost_tracker import ContentCache


class TableVisionParser:
    """Parses PDF tables via Gemini 2.5 Vision, enriches with Markdown/Q&A, and caches by SHA-256."""

    def __init__(
        self,
        gateway: ModelGateway,
        crops_dir: Path,
        cache_dir: Path,
        model: str = "gemini-2.5-flash",
    ) -> None:
        self.gateway = gateway
        self.crops_dir = crops_dir
        self.crops_dir.mkdir(parents=True, exist_ok=True)
        self.table_cache = ContentCache(cache_dir / "tables")
        self.model = model

    def parse_table(
        self,
        region: TableRegion,
        page: LoadedPdfPage,
        doc_id: str,
        section_type: SectionType,
        section_title: str,
        table_idx: int = 1,
    ) -> ExtractedTableArtifact:
        """Extract table from image crop with SHA-256 disk caching."""
        # Crop table bounding box with 16pt margin to capture headers/footnotes
        margin = 16.0
        clip_bbox = (
            max(0.0, region.bbox[0] - margin),
            max(0.0, region.bbox[1] - margin),
            min(page.width, region.bbox[2] + margin),
            min(page.height, region.bbox[3] + margin),
        )
        crop_filename = f"{doc_id}_p{page.page_number}_t{table_idx}.png"
        crop_path = self.crops_dir / crop_filename
        png_bytes = page.render_png(dpi=200, clip_bbox=clip_bbox)
        crop_path.write_bytes(png_bytes)

        # Hash image bytes for content-addressable cache
        sha_hash = hashlib.sha256(png_bytes).hexdigest()
        cached = self.table_cache.get(sha_hash)

        if cached is not None and isinstance(cached, dict):
            return ExtractedTableArtifact.model_validate(cached)

        # Vision extraction pass
        rows_hint = json.dumps(region.raw_rows) if region.raw_rows else "[]"
        res = self.gateway.generate(
            task="table_extract",
            model=self.model,
            instruction=(
                "Extract this Indian Insurance policy table into clean Markdown and structured rows. "
                "Preserve all column headers, sub-limits, percentage co-pays, and footnotes. "
                "Generate 5-10 synthetic question-answer pairs covering specific numbers and limits."
            ),
            schema=TableExtractionDraft,
            operation="ingest.table_extract",
            images=(png_bytes,),
            hints={
                "section_title": section_title,
                "rows_json": rows_hint,
                "footnotes": "\n".join(
                    ln for ln in page.raw_text.splitlines() if ln.strip().startswith("*")
                ),
            },
        )

        draft = res.parsed
        artifact = ExtractedTableArtifact(
            table_id=f"tbl_{doc_id}_p{page.page_number}_{table_idx}",
            doc_id=doc_id,
            page_number=page.page_number,
            section_type=section_type,
            title=draft.title,
            summary=draft.summary,
            markdown_table=draft.markdown_table,
            structured_rows=draft.structured_rows,
            footnotes=draft.footnotes,
            synthetic_qa_pairs=draft.synthetic_qa_pairs,
            image_crop_path=str(crop_path),
            sha256_hash=sha_hash,
        )

        # Cache extracted artifact
        self.table_cache.put(sha_hash, artifact.model_dump(mode="json"))
        return artifact

    def create_table_child_chunks(
        self,
        artifact: ExtractedTableArtifact,
        parent_id: str,
        policy_name: str,
        insurer_name: str,
        uin: str,
    ) -> list[ChildChunk]:
        """Convert an extracted table into child chunks for high-recall vector search."""
        chunks: list[ChildChunk] = []

        # 1. Full table summary chunk
        table_summary_text = (
            f"TABLE: {artifact.title}\n"
            f"SUMMARY: {artifact.summary}\n\n"
            f"{artifact.markdown_table}\n"
            f"{'Footnotes: ' + '; '.join(artifact.footnotes) if artifact.footnotes else ''}"
        )
        meta = ChunkMetadata(
            doc_id=artifact.doc_id,
            policy_name=policy_name,
            insurer_name=insurer_name,
            uin=uin,
            section_type=artifact.section_type,
            section_title=artifact.title,
            page_number=artifact.page_number,
            chunk_type=ChunkType.TABLE,
            parent_id=parent_id,
            image_crop_path=artifact.image_crop_path,
            sha256_hash=artifact.sha256_hash,
        )
        chunks.append(
            ChildChunk(
                chunk_id=f"{artifact.table_id}_summary",
                text=table_summary_text,
                embedding_input=f"{artifact.title}. {artifact.summary} {table_summary_text[:400]}",
                metadata=meta,
            )
        )

        # 2. Synthetic Q&A child chunks
        for q_idx, qa in enumerate(artifact.synthetic_qa_pairs):
            qa_text = f"Q: {qa.question}\nA: {qa.answer} [Table: {artifact.title}, Page {artifact.page_number}]"
            qa_meta = ChunkMetadata(
                doc_id=artifact.doc_id,
                policy_name=policy_name,
                insurer_name=insurer_name,
                uin=uin,
                section_type=artifact.section_type,
                section_title=f"{artifact.title} (Q&A {q_idx + 1})",
                page_number=artifact.page_number,
                chunk_type=ChunkType.TABLE,
                parent_id=parent_id,
                image_crop_path=artifact.image_crop_path,
                sha256_hash=hashlib.sha256(qa_text.encode("utf-8")).hexdigest(),
            )
            chunks.append(
                ChildChunk(
                    chunk_id=f"{artifact.table_id}_qa_{q_idx + 1}",
                    text=qa_text,
                    embedding_input=f"{qa.question} {qa.answer}",
                    metadata=qa_meta,
                )
            )

        return chunks
