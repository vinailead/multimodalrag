"""PDF document loader, layout extractor, and high-DPI visual rendering using PyMuPDF."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pymupdf

from insurance_mmrag.schemas import TableRegion, TextBlock
from insurance_mmrag.security.sanitizer import PdfSanitizer


class LoadedPdfPage:
    def __init__(
        self,
        page_number: int,
        width: float,
        height: float,
        raw_text: str,
        blocks: list[TextBlock],
        tables: list[TableRegion],
        _pymupdf_page: Any,
    ) -> None:
        self.page_number = page_number
        self.width = width
        self.height = height
        self.raw_text = raw_text
        self.blocks = blocks
        self.tables = tables
        self._page = _pymupdf_page

    def render_png(
        self, dpi: int = 200, clip_bbox: tuple[float, float, float, float] | None = None
    ) -> bytes:
        """Render page or sub-region as PNG image bytes."""
        matrix = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)
        clip = pymupdf.Rect(*clip_bbox) if clip_bbox else None
        pix = self._page.get_pixmap(matrix=matrix, clip=clip)
        return cast(bytes, pix.tobytes("png"))

    def save_crop(
        self, output_path: Path, bbox: tuple[float, float, float, float], dpi: int = 200
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = self.render_png(dpi=dpi, clip_bbox=bbox)
        output_path.write_bytes(data)
        return output_path


class PdfLoader:
    """Safely loads and extracts structured layout data from PDF documents."""

    def __init__(self, sanitizer: PdfSanitizer | None = None) -> None:
        self.sanitizer = sanitizer or PdfSanitizer()

    def load(self, pdf_path: Path) -> tuple[Any, list[LoadedPdfPage]]:
        data = self.sanitizer.validate_pdf_file(pdf_path)
        doc: Any = pymupdf.open(stream=data, filetype="pdf")
        pages: list[LoadedPdfPage] = []

        for p_idx in range(len(doc)):
            page = doc[p_idx]
            page_num = p_idx + 1
            raw_text = cast(str, page.get_text("text"))
            blocks = self._extract_blocks(page, page_num)
            tables = self._extract_tables(page, page_num)
            pages.append(
                LoadedPdfPage(
                    page_number=page_num,
                    width=float(page.rect.width),
                    height=float(page.rect.height),
                    raw_text=raw_text,
                    blocks=blocks,
                    tables=tables,
                    _pymupdf_page=page,
                )
            )

        return doc, pages

    def _extract_blocks(self, page: Any, page_num: int) -> list[TextBlock]:
        blocks: list[TextBlock] = []
        page_dict: Any = page.get_text("dict")
        for b in page_dict.get("blocks", []):
            if b.get("type") == 0:  # text block
                bbox = tuple(float(x) for x in b.get("bbox", (0, 0, 0, 0)))
                text_parts: list[str] = []
                max_size = 0.0
                is_bold = False

                for line in b.get("lines", []):
                    for span in line.get("spans", []):
                        span_text = span.get("text", "")
                        text_parts.append(span_text)
                        sz = float(span.get("size", 0.0))
                        if sz > max_size:
                            max_size = sz
                        flags = int(span.get("flags", 0))
                        font = str(span.get("font", "")).lower()
                        if (flags & 2 != 0) or ("bold" in font) or ("black" in font):
                            is_bold = True

                full_block_text = "".join(text_parts).strip()
                if full_block_text:
                    blocks.append(
                        TextBlock(
                            page_number=page_num,
                            text=full_block_text,
                            font_size=round(max_size, 2),
                            is_bold=is_bold,
                            bbox=cast(tuple[float, float, float, float], bbox),
                        )
                    )
        return blocks

    def _extract_tables(self, page: Any, page_num: int) -> list[TableRegion]:
        regions: list[TableRegion] = []
        try:
            tabs = page.find_tables()
            for t in tabs.tables:
                bbox = tuple(float(x) for x in t.bbox)
                rows: list[list[str]] = []
                for row in t.extract():
                    rows.append([str(c or "").strip() for c in row])
                regions.append(
                    TableRegion(
                        page_number=page_num,
                        bbox=cast(tuple[float, float, float, float], bbox),
                        raw_rows=rows,
                    )
                )
        except (AttributeError, ValueError, RuntimeError):
            # Page layout engine does not support table detection for this page
            regions.clear()

        # Fallback: if find_tables found nothing, inspect vector graphics rectangles
        if not regions:
            drawings = page.get_drawings()
            rects = [
                d["rect"]
                for d in drawings
                if "rect" in d and d["rect"].width > 200 and d["rect"].height > 80
            ]
            if rects:
                # Union the drawings to find table boundary
                r = rects[0]
                for other in rects[1:]:
                    r |= other
                bbox = (float(r.x0), float(r.y0), float(r.x1), float(r.y1))
                regions.append(
                    TableRegion(
                        page_number=page_num,
                        bbox=bbox,
                        raw_rows=[],
                    )
                )
        return regions
