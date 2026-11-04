"""DPDP Act 2023 PII redaction for Indian identifiers.

Runs before any text is logged, embedded, or sent to an external model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Ordered: most specific patterns first so a 12-digit Aadhaar is never half-matched as a phone.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    (
        "POLICY_ID",
        re.compile(
            r"\b(?:POL|UHID|CLAIM|CLM|MEMBER)[-/]?[A-Z0-9]{6,16}\b"
            r"|\bpolicy\s*(?:no|number|#)\.?\s*[:\-]?\s*[A-Z0-9/-]{6,20}\b",
            re.IGNORECASE,
        ),
    ),
    ("AADHAAR", re.compile(r"(?<![a-zA-Z\d\\+])\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")),
    ("PAN", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")),
    ("PHONE", re.compile(r"(?:\+91[\s-]?|\b0)?(?<!\d)[6-9]\d{9}\b")),
)


def _empty_categories() -> list[str]:
    return []


@dataclass(frozen=True)
class RedactionResult:
    redacted_text: str
    categories: list[str] = field(default_factory=_empty_categories)
    match_count: int = 0

    @property
    def was_redacted(self) -> bool:
        return self.match_count > 0


class PiiRedactor:
    """Deterministically masks Aadhaar, PAN, Indian mobile, email and policy/UHID numbers."""

    def redact(self, text: str) -> RedactionResult:
        categories: list[str] = []
        total = 0
        redacted = text
        for label, pattern in _PATTERNS:
            redacted, count = pattern.subn(f"[REDACTED_{label}]", redacted)
            if count:
                categories.append(label)
                total += count
        return RedactionResult(redacted_text=redacted, categories=categories, match_count=total)
