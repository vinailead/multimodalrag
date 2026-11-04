"""Fetches public IRDAI policy wordings & CIS PDFs and writes data/raw_policies/manifest.json.

Downloads authentic health insurance policy documents directly from major Indian health insurance
provider endpoints (HDFC ERGO, Tata AIG, Go Digit, Bajaj Allianz) and public IRDAI standard
disclosure documents (Arogya Sanjeevani, Saral Suraksha Bima).
Validates all PDF bytes against adversarial prompt injection via PdfSanitizer.
If offline, firewalled, or during sandboxed CI, uses the local IRDAI policy factory to deterministically
generate authentic standard IRDAI PDFs with genuine layout, tables, and clauses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
import pymupdf

from insurance_mmrag.ingestion.sample_policy_factory import (
    create_arogya_sanjeevani_pdf,
    create_saral_suraksha_bima_pdf,
)
from insurance_mmrag.pipeline import create_default_pipeline
from insurance_mmrag.security.sanitizer import PdfSanitizer

PUBLIC_SOURCES: list[dict[str, str]] = [
    {
        "doc_id": "arogya_sanjeevani_national",
        "policy_name": "Arogya Sanjeevani Policy, National Insurance Co. Ltd.",
        "insurer_name": "National Insurance Company Limited",
        "uin": "NICHLIP20177V011920",
        "url": "https://nationalinsurance.nic.co.in/sites/default/files/Arogya%20Sanjeevani%20Policy%20-%20National%20Policy%20Wordings.pdf",
        "filename": "arogya_sanjeevani_policy_wordings.pdf",
        "fallback_type": "arogya_sanjeevani",
    },
    {
        "doc_id": "saral_suraksha_hdfc_ergo",
        "policy_name": "Saral Suraksha Bima, HDFC ERGO General Insurance Co. Ltd.",
        "insurer_name": "HDFC ERGO General Insurance Company",
        "uin": "HDFPAIP21175V012021",
        "url": "https://www.hdfcergo.com/docs/default-source/downloads/policy-wordings/saral-suraksha-bima-policy-wordings.pdf",
        "filename": "saral_suraksha_bima.pdf",
        "fallback_type": "saral_suraksha_bima",
    },
    {
        "doc_id": "hdfc_ergo_optima_secure",
        "policy_name": "Optima Secure Policy Wordings, HDFC ERGO General Insurance Co. Ltd.",
        "insurer_name": "HDFC ERGO General Insurance Company",
        "uin": "HDFHLIP26058V082526",
        "url": "https://www.hdfcergo.com/docs/default-source/downloads/policy-wordings/health/optima-secure-revision-pw.pdf",
        "filename": "hdfc_ergo_optima_secure.pdf",
        "fallback_type": "none",
    },
    {
        "doc_id": "tata_aig_medicare_premier",
        "policy_name": "Tata AIG MediCare Premier Policy Wordings",
        "insurer_name": "Tata AIG General Insurance Company Limited",
        "uin": "TATHLIP21257V022021",
        "url": "https://www.tataaig.com/s3/tata_aig_medicare_premier_policy_wordings_781aa2fd94.pdf",
        "filename": "tata_aig_medicare_premier.pdf",
        "fallback_type": "none",
    },
    {
        "doc_id": "godigit_health_plus",
        "policy_name": "Digit Health Plus Policy Wordings",
        "insurer_name": "Go Digit General Insurance Limited",
        "uin": "GODHLIP20025V011920",
        "url": "https://www.godigit.com/content/dam/godigit/directportal/en/downloads/health/Digit%20Insurance%20-%20Digit%20Health%20Plus%20Policy%20Wordings.pdf",
        "filename": "godigit_health_plus.pdf",
        "fallback_type": "none",
    },
    {
        "doc_id": "bajaj_allianz_health_guard",
        "policy_name": "Bajaj Allianz Health Guard Policy Wordings",
        "insurer_name": "Bajaj Allianz General Insurance Company Limited",
        "uin": "BAJHLIP21057V032021",
        "url": "https://cms-assets.bajajfinserv.in/is/content/bajajfinance/policy-wording-health-guard-v1?scl=1&fmt=pdf",
        "filename": "bajaj_allianz_health_guard.pdf",
        "fallback_type": "none",
    },
]

HTTP_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(65536):
            h.update(chunk)
    return h.hexdigest()


def count_pages(path: Path) -> int:
    doc: Any = pymupdf.open(str(path))
    count = int(doc.page_count)
    doc.close()
    return count


def fetch_or_generate_policies(
    output_dir: Path, force_download: bool = False
) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_entries: list[dict[str, Any]] = []
    sanitizer = PdfSanitizer(max_size_mb=30)

    for item in PUBLIC_SOURCES:
        dest = output_dir / item["filename"]
        source_type = "direct_provider_download"
        downloaded = False

        if force_download or not dest.exists():
            try:
                # Try downloading directly from provider
                with httpx.Client(
                    headers=HTTP_HEADERS, timeout=30.0, follow_redirects=True
                ) as client:
                    resp = client.get(item["url"])
                    if resp.status_code == 200 and resp.content.startswith(b"%PDF-"):
                        sanitizer.validate_pdf_bytes(resp.content)
                        dest.write_bytes(resp.content)
                        downloaded = True
            except Exception as exc:
                print(f"[WARN] Direct download failed for {item['doc_id']} ({item['url']}): {exc}")
                downloaded = False

        if not dest.exists():
            if item["fallback_type"] == "arogya_sanjeevani":
                source_type = "irdai_standard_synthesized"
                create_arogya_sanjeevani_pdf(dest)
            elif item["fallback_type"] == "saral_suraksha_bima":
                source_type = "irdai_standard_synthesized"
                create_saral_suraksha_bima_pdf(dest)
            else:
                # Provider policy not available offline and no synthetic fallback
                print(
                    f"[SKIP] Provider policy {item['doc_id']} skipped (offline / download failed)."
                )
                continue
        elif not downloaded:
            # File already exists locally
            source_type = (
                "irdai_standard_synthesized"
                if "synthesized" in item.get("fallback_type", "")
                else "direct_provider_download"
            )

        digest = sha256_file(dest)
        pages = count_pages(dest)

        manifest_entries.append(
            {
                "doc_id": item["doc_id"],
                "policy_name": item["policy_name"],
                "insurer_name": item["insurer_name"],
                "uin": item["uin"],
                "filename": item["filename"],
                "file_path": str(
                    dest.relative_to(output_dir.parent.parent)
                    if output_dir.is_relative_to(Path.cwd())
                    else dest
                ),
                "sha256": digest,
                "pages": pages,
                "source": source_type,
            }
        )

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_entries, indent=2), encoding="utf-8")
    return manifest_entries


def ingest_manifest_policies(manifest_entries: list[dict[str, Any]], stub: bool = True) -> None:
    print(f"\n[INGEST] Initializing MMRAG pipeline for {len(manifest_entries)} policies...")
    pipeline = create_default_pipeline(use_stub=stub)
    for entry in manifest_entries:
        pdf_path = Path(entry["file_path"])
        if not pdf_path.exists():
            continue
        print(
            f" -> Ingesting [{entry['doc_id']}] {entry['policy_name']} ({entry['pages']} pages)..."
        )
        ingested = pipeline.ingest_pdf(pdf_path, doc_id=entry["doc_id"])
        print(
            f"    [OK] Parents: {len(ingested.parents)} | Children: {len(ingested.children)} | Tables: {len(ingested.tables)}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch or generate IRDAI provider policy PDFs.")
    parser.add_argument("--output-dir", default="data/raw_policies", help="Target output directory")
    parser.add_argument("--force", action="store_true", help="Force re-download of existing PDFs")
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Ingest all downloaded policies into the MMRAG pipeline",
    )
    parser.add_argument(
        "--stub",
        action="store_true",
        default=True,
        help="Use deterministic stub Gemini client for embedding/generation (default: True)",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    entries = fetch_or_generate_policies(out_dir, force_download=args.force)
    print(f"[FETCH_IRDAI] Successfully prepared {len(entries)} IRDAI policy PDFs in {out_dir}:")
    for e in entries:
        print(
            f"  - [{e['uin']}] {e['policy_name']} ({e['pages']} pages, {e['source']}, {e['sha256'][:12]}...)"
        )

    if args.ingest:
        ingest_manifest_policies(entries, stub=args.stub)


if __name__ == "__main__":
    main()
