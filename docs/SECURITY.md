# docs/SECURITY.md — Threat Model, DPDP Act 2023 PII Protection & Guardrails

Zero generalization is permitted in handling policyholder data, document ingestion, or external LLM calls. This system implements defense-in-depth aligned with **India's Digital Personal Data Protection (DPDP) Act, 2023**, **IRDAI Cybersecurity Guidelines**, and **OWASP Top 10 for LLM Applications**.

---

## 1. DPDP Act 2023 PII / PHI Redaction Engine (`src/insurance_mmrag/security/pii_redactor.py`)

Before any user query or uploaded document snippet is logged or transmitted to an external embedding or generation endpoint, `PiiRedactor` deterministically detects and masks Indian Personal Identifiable Information (PII) and Protected Health Information (PHI) identifiers:

| Identifier Type | Pattern / Detection Rule | Replacement Token |
| :--- | :--- | :--- |
| **Aadhaar Number** | 12-digit UIDAI format (`\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b`) | `[REDACTED_AADHAAR]` |
| **PAN Card Number** | Income Tax Department format (`\b[A-Z]{5}[0-9]{4}[A-Z]\b`) | `[REDACTED_PAN]` |
| **Indian Mobile Number** | `+91` / `0` prefixed 10-digit mobile (`(?:\+91[\s-]?)?[6-9]\d{9}\b`) | `[REDACTED_PHONE]` |
| **Email Address** | RFC 5322 email pattern | `[REDACTED_EMAIL]` |
| **Policy / UHID Number** | Explicit policy/member/claim ID patterns (`(?:POL|UHID|CLAIM)[-/]?[A-Z0-9]{6,16}`) | `[REDACTED_POLICY_ID]` |

All redacted categories are returned in `GroundedQueryResponse.pii_redactions_applied` and displayed in the UI's DPDP Act 2023 notification banner so the user has transparent proof that their sensitive identifiers were stripped prior to model inference.

---

## 2. Indirect Prompt Injection & PDF Sanitization (`src/insurance_mmrag/security/sanitizer.py`)

Untrusted PDFs can embed invisible or adversarial text designed to hijack RAG instructions (OWASP LLM01: Prompt Injection).
1. **PDF Magic-Byte & Size Validation**: Verifies `%PDF-` header bytes, rejects files exceeding `MAX_PDF_SIZE_MB` (default `50 MB`), and blocks encrypted/JavaScript-bearing PDF objects (`/JS`, `/JavaScript`, `/Launch`).
2. **Adversarial Instruction Stripping**: Scans extracted text blocks and user queries for prompt-injection signatures (e.g., *"ignore all previous instructions"*, *"system override"*, *"approve this claim unconditionally"*, *"you are now an unrestricted assistant"*), neutralizes the payload, and logs a `SECURITY_PROMPT_INJECTION_DETECTED` event in the immutable audit trail.
3. **Strict Structural Delimiting**: Assembled parent chunks are wrapped in XML-escaped `<policy_evidence id="...">` tags in the system prompt with explicit instructions that content inside `<policy_evidence>` is passive contractual data, never executable instructions.

---

## 3. Static Application Security Testing (SAST) & Dependency Hygiene

- **`bandit`**: Executed automatically on every `npm run check` and git pre-commit (`uv run bandit -c pyproject.toml -r src/ scripts/`). Zero high/medium severity findings permitted.
- **Secret Isolation**: `GEMINI_API_KEY` is loaded strictly from environment variables via `pydantic-settings`. Hardcoded API keys or tokens are blocked by Ruff (`S105`, `S106`) and Bandit.
- **Deterministic Lockfiles**: Both `uv.lock` (Python) and `package-lock.json` (Node/TypeScript) are committed and verified.
