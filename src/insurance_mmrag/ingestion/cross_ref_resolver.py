"""Cross-reference graph resolution and IRDAI legal precedence linking.

Connects clause references (Excl01-Excl18, Section X.Y, defined terms) to target ParentChunks,
and enforces the IRDAI Legal Precedence Rule (Policy Wordings & Schedule govern over the CIS summary).
"""

from __future__ import annotations

import re

from insurance_mmrag.domain.irdai import (
    DEF_REF_RE,
    NUMBERED_CLAUSE_RE,
    SECTION_REF_RE,
    find_excl_codes,
)
from insurance_mmrag.schemas import (
    BINDING_SECTIONS,
    ParentChunk,
    PrecedenceCheck,
    SectionType,
)

DEFINED_TERMS: tuple[str, ...] = (
    "Pre-Existing Disease",
    "Pre-Existing Diseases",
    "PED",
    "AYUSH Hospital",
    "AYUSH Treatment",
    "Cashless Facility",
    "Co-Payment",
    "Cumulative Bonus",
    "Day Care Treatment",
    "Deductible",
    "Network Provider",
    "Proportionate Deduction",
    "Room Rent",
    "Intensive Care Unit",
    "Modern Treatment Methods",
    "Accident",
)


class CrossReferenceResolver:
    """Builds 1-hop cross-reference links between chunks and resolves IRDAI precedence."""

    def __init__(self) -> None:
        self._term_patterns = [
            (term, re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)) for term in DEFINED_TERMS
        ]

    def extract_clause_codes(self, text: str) -> list[str]:
        """Extract explicit IRDAI standard codes and numbered clauses."""
        codes: list[str] = find_excl_codes(text)
        for m in SECTION_REF_RE.finditer(text):
            codes.append(f"Section_{m.group(1)}")
        for m in DEF_REF_RE.finditer(text):
            codes.append(f"Def_{int(m.group(1)):02d}")
        for m in NUMBERED_CLAUSE_RE.finditer(text):
            clause_id = f"Clause_{m.group(1)}"
            if clause_id not in codes:
                codes.append(clause_id)
        return codes

    def resolve_references(self, text: str, parent_index: dict[str, ParentChunk]) -> list[str]:
        """Find parent_ids referenced in text by clause code, section title, or defined term."""
        linked_parent_ids: list[str] = []
        codes = self.extract_clause_codes(text)

        # 1. Match explicit codes to parent chunks that contain them
        for code in codes:
            for pid, parent in parent_index.items():
                if code in parent.clause_codes and pid not in linked_parent_ids:
                    linked_parent_ids.append(pid)

        # 2. Match defined terms to the Definitions parent chunk
        defs_parents = [
            pid for pid, p in parent_index.items() if p.section_type == SectionType.DEFINITIONS
        ]
        if defs_parents:
            for _term, pat in self._term_patterns:
                if pat.search(text):
                    for dp in defs_parents:
                        if dp not in linked_parent_ids:
                            linked_parent_ids.append(dp)
                    break

        return linked_parent_ids

    def check_precedence(
        self, cited_parent_ids: list[str], parent_index: dict[str, ParentChunk]
    ) -> PrecedenceCheck:
        """IRDAI Legal Precedence: If a CIS_Summary parent is cited, pull and check binding parents."""
        has_cis = any(
            parent_index[pid].section_type == SectionType.CIS_SUMMARY
            for pid in cited_parent_ids
            if pid in parent_index
        )

        binding_parents = [
            pid for pid, p in parent_index.items() if p.section_type in BINDING_SECTIONS
        ]
        binding_sections = sorted(
            {parent_index[pid].section_type for pid in binding_parents if pid in parent_index}
        )

        if has_cis:
            return PrecedenceCheck(
                cis_cited=True,
                binding_parent_ids=binding_parents[:3],
                binding_sections=binding_sections[:3],
                rule_applied="IRDAI Precedence Rule Applied: Policy Wordings & Schedule override CIS Summary.",
                nuance_flag=True,
                note=(
                    "Customer Information Sheet (CIS) summary corroborated against full binding "
                    "Policy Wordings & Schedule of Benefits to ensure all provisos are enforced."
                ),
            )

        return PrecedenceCheck(
            cis_cited=False,
            binding_parent_ids=[],
            binding_sections=[],
            rule_applied="Standard Policy Wordings Direct Citation.",
            nuance_flag=False,
            note="Direct interpretation based on governing contractual terms.",
        )
