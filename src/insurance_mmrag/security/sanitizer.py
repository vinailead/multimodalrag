"""PDF validation and indirect prompt-injection neutralization (OWASP LLM01)."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path

_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above)\s+instructions?",
        r"disregard\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above|system)\s+\w+",
        r"system\s+override",
        r"you\s+are\s+now\s+(?:an?\s+)?(?:unrestricted|jailbroken|dan)\b[\w\s]*",
        r"approve\s+(?:this|the|all)\s+claims?(?:\s+unconditionally)?",
        r"reveal\s+(?:your\s+)?(?:system\s+prompt|hidden\s+instructions)",
        r"<\s*/?\s*(?:system|policy_evidence)\s*>",
    )
)

_DANGEROUS_PDF_TOKENS: tuple[bytes, ...] = (b"/JavaScript", b"/JS ", b"/JS(", b"/Launch")
NEUTRALIZED = "[NEUTRALIZED_INSTRUCTION]"


class PdfValidationError(ValueError):
    """Raised when an uploaded PDF fails structural or safety validation."""


def _empty_signatures() -> list[str]:
    return []


@dataclass(frozen=True)
class SanitizationResult:
    clean_text: str
    injection_detected: bool
    matched_signatures: list[str] = field(default_factory=_empty_signatures)


class PdfSanitizer:
    """Validates PDF bytes and neutralizes adversarial instructions in extracted text/queries."""

    def __init__(self, max_size_mb: int = 50) -> None:
        self._max_bytes = max_size_mb * 1024 * 1024

    def validate_pdf_bytes(self, data: bytes) -> None:
        if not data.startswith(b"%PDF-"):
            raise PdfValidationError("File is not a PDF (missing %PDF- magic bytes).")
        if len(data) > self._max_bytes:
            raise PdfValidationError(f"PDF exceeds maximum size of {self._max_bytes} bytes.")
        for token in _DANGEROUS_PDF_TOKENS:
            if token in data:
                raise PdfValidationError(f"PDF contains forbidden active content: {token!r}.")

    def validate_pdf_file(self, path: Path) -> bytes:
        data = path.read_bytes()
        self.validate_pdf_bytes(data)
        return data

    def sanitize_text(self, text: str) -> SanitizationResult:
        matched: list[str] = []
        clean = text
        for pattern in _INJECTION_PATTERNS:
            found = pattern.findall(clean)
            if found:
                matched.extend(str(f) for f in found)
                clean = pattern.sub(NEUTRALIZED, clean)
        return SanitizationResult(
            clean_text=clean, injection_detected=bool(matched), matched_signatures=matched
        )

    @staticmethod
    def wrap_evidence(evidence_id: str, text: str) -> str:
        """Wrap passive contractual evidence in escaped delimiters for the system prompt."""
        return (
            f'<policy_evidence id="{html.escape(evidence_id, quote=True)}">\n'
            f"{html.escape(text, quote=False)}\n</policy_evidence>"
        )
