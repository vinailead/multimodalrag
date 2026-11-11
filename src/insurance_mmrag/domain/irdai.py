"""IRDAI domain knowledge: section taxonomy rules, clause codes, synonyms and intent cues.

Shared by the structure analyzer, intent router, retrieval tokenizer and the test stub so that
heuristics live in exactly one place.
"""

from __future__ import annotations

import re

from insurance_mmrag.schemas import SectionType

# Ordered: earlier rules win (e.g. "Waiting Period" headings must not fall into Exclusions).
SECTION_HEADING_RULES: tuple[tuple[SectionType, re.Pattern[str]], ...] = tuple(
    (section, re.compile(pattern, re.IGNORECASE))
    for section, pattern in (
        (SectionType.CIS_SUMMARY, r"customer\s+information\s+sheet|key\s+features|\bCIS\b"),
        (
            SectionType.SCHEDULE_OF_BENEFITS,
            r"schedule\s+of\s+benefits|benefit\s+schedule|table\s+of\s+benefits|policy\s+schedule",
        ),
        (SectionType.DEFINITIONS, r"\bdefinitions?\b"),
        (SectionType.WAITING_PERIODS, r"waiting\s+periods?"),
        (SectionType.EXCLUSIONS, r"exclusions?|what\s+is\s+not\s+covered"),
        (
            SectionType.COST_SHARING,
            r"co-?pay(?:ment)?|deductibles?|cost\s+sharing|proportionate\s+deduction",
        ),
        (SectionType.OPTIONAL_RIDERS, r"optional|add-?on|riders?"),
        (SectionType.CLAIMS_AND_GRIEVANCE, r"claims?|grievance|ombudsman|redressal"),
        (
            SectionType.BASE_COVERAGE,
            r"coverage|benefits?\s+covered|what\s+is\s+covered|scope\s+of\s+cover|in-?patient",
        ),
    )
)

EXCL_CODE_RE = re.compile(r"\bExcl\s?-?0?(\d{1,2})\b", re.IGNORECASE)
SECTION_REF_RE = re.compile(r"\b(?:Section|Clause)\s+(\d+(?:\.\d+)*(?:\([a-z]\))?)", re.IGNORECASE)
DEF_REF_RE = re.compile(r"\bDef(?:inition)?\.?\s*(\d{1,2})\b", re.IGNORECASE)
NUMBERED_CLAUSE_RE = re.compile(r"^\s*(\d+(?:\.\d+)+)\s+", re.MULTILINE)

# IRDAI standard exclusion codes (Guidelines on Standardization of Exclusions in Health Insurance).
IRDAI_STANDARD_EXCLUSIONS: dict[str, str] = {
    "Excl01": "Pre-Existing Diseases",
    "Excl02": "Specified disease/procedure waiting period",
    "Excl03": "30-day initial waiting period",
    "Excl04": "Investigation & Evaluation",
    "Excl05": "Rest Cure, rehabilitation and respite care",
    "Excl06": "Obesity/ Weight Control",
    "Excl07": "Change-of-Gender treatments",
    "Excl08": "Cosmetic or plastic Surgery",
    "Excl09": "Hazardous or Adventure sports",
    "Excl10": "Breach of law",
    "Excl11": "Excluded Providers",
    "Excl12": "Alcoholism, drug or substance abuse",
    "Excl13": "Treatments in health hydros, nature cure clinics, spas",
    "Excl14": "Dietary supplements and substances purchased without prescription",
    "Excl15": "Refractive Error",
    "Excl16": "Unproven Treatments",
    "Excl17": "Sterility and Infertility",
    "Excl18": "Maternity",
}

SYNONYMS: dict[str, str] = {
    "ped": "preexisting",
    "pre-existing": "preexisting",
    "preexisting": "preexisting",
    "hospitalisation": "hospitalization",
    "hospitalised": "hospitalized",
    "si": "suminsured",
    "copay": "copay",
    "co-pay": "copay",
    "co-payment": "copay",
    "copayment": "copay",
    "lac": "lakh",
    "lacs": "lakh",
    "lakhs": "lakh",
    "ayurveda": "ayush",
    "homeopathy": "ayush",
    "op": "outpatient",
    "opd": "outpatient",
    "icu": "icu",
}

STOPWORDS: frozenset[str] = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "is",
        "it",
        "its",
        "my",
        "of",
        "on",
        "or",
        "our",
        "the",
        "this",
        "to",
        "under",
        "what",
        "when",
        "which",
        "who",
        "will",
        "with",
        "would",
        "me",
        "you",
        "your",
        "there",
        "any",
        "per",
        "after",
        "before",
        "am",
        "was",
        "were",
    ]
)

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-]*", re.IGNORECASE)


def normalize_clause_code(raw: str) -> str | None:
    m = EXCL_CODE_RE.search(raw)
    if not m:
        return None
    return f"Excl{int(m.group(1)):02d}"


def find_excl_codes(text: str) -> list[str]:
    seen: list[str] = []
    for m in EXCL_CODE_RE.finditer(text):
        code = f"Excl{int(m.group(1)):02d}"
        if code not in seen:
            seen.append(code)
    return seen


def tokenize(text: str) -> list[str]:
    """Domain tokenizer: lowercase, synonym-normalized, stopword-free, light plural stemming."""
    tokens: list[str] = []
    for raw in TOKEN_RE.findall(text.lower()):
        tok = SYNONYMS.get(raw) or raw
        if tok.startswith("excl"):
            code = normalize_clause_code(tok)
            if code is not None:
                tok = code.lower()
        tok = tok.replace("-", "")
        if tok in STOPWORDS or not tok:
            continue
        if len(tok) > 4 and tok.endswith("s") and not tok.endswith("ss"):
            tok = tok[:-1]
        tokens.append(tok)
    return tokens


def classify_heading(text: str) -> SectionType | None:
    for section, pattern in SECTION_HEADING_RULES:
        if pattern.search(text):
            return section
    return None


# --------------------------------------------------------------------------- intent cues
INTENT_CUES: tuple[tuple[SectionType, re.Pattern[str]], ...] = tuple(
    (section, re.compile(pattern, re.IGNORECASE))
    for section, pattern in (
        (
            SectionType.WAITING_PERIODS,
            r"waiting|how\s+long|months?|years?\s+after|pre-?existing|\bPED\b|Excl\s?0?[123]\b|"
            r"cataract|hernia|hydrocele|piles|sinusitis|joint\s+replacement",
        ),
        (
            SectionType.EXCLUSIONS,
            r"exclu|not\s+covered|cosmetic|obesity|adventure|Excl\s?\d|infertility|refractive",
        ),
        (
            SectionType.SCHEDULE_OF_BENEFITS,
            r"room\s+rent|\bICU\b|sub-?limit|\blimit|sum\s+insured|lakh|₹|rs\.?|%|percent|"
            r"plan|variant|slab|how\s+much|amount|cataract",
        ),
        (
            SectionType.COST_SHARING,
            r"co-?pay|deductible|proportionate|out\s+of\s+pocket|room\s+rent|deduct",
        ),
        (
            SectionType.CLAIMS_AND_GRIEVANCE,
            r"claim|cashless|reimburse|document|grievance|ombudsman|intimat|complain|bima\s+bharosa",
        ),
        (SectionType.DEFINITIONS, r"defin|meaning|what\s+(?:is|does)\s+.+\s+mean|\bterm\b"),
        (
            SectionType.BASE_COVERAGE,
            r"cover|benefit|ayush|day\s*care|restore|hospitali[sz]|surgery|treatment|ambulance|"
            r"domiciliary|modern\s+treatment|robotic|cataract",
        ),
        (SectionType.OPTIONAL_RIDERS, r"rider|add-?on|optional|maternity|\bOPD\b|outpatient"),
        (SectionType.CIS_SUMMARY, r"summary|key\s+features|overview|\bCIS\b"),
    )
)

TABLE_BOOST_RE = re.compile(
    r"room\s+rent|\bICU\b|sub-?limit|\blimit|sum\s+insured|lakh|₹|rs\.?\s*\d|%|percent|"
    r"how\s+much|amount|slab|plan\s+variant|table",
    re.IGNORECASE,
)

SUBQUERY_SPLIT_RE = re.compile(
    r"\?\s+|;\s*|,\s*and\s+|\s+and\s+(?=(?:what|is|does|how|are|can|will)\b)|\s+also\s+",
    re.IGNORECASE,
)
