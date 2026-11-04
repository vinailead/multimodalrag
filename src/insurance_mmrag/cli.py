"""Rich CLI for Indian Insurance Multimodal RAG."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from insurance_mmrag.config import get_settings
from insurance_mmrag.evals.benchmark_runner import BenchmarkRunner
from insurance_mmrag.ingestion.sample_policy_factory import create_arogya_sanjeevani_pdf
from insurance_mmrag.pipeline import create_default_pipeline

console = Console()


def cmd_ingest(args: argparse.Namespace) -> None:
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        console.print(f"[bold red]File not found:[/bold red] {pdf_path}")
        sys.exit(1)

    console.print(f"[bold blue]Ingesting policy document:[/bold blue] {pdf_path}")
    pipeline = create_default_pipeline(use_stub=args.stub)
    ingested = pipeline.ingest_pdf(pdf_path, doc_id=args.doc_id)

    console.print(
        Panel(
            f"[bold green]Document Ingested Successfully![/bold green]\n"
            f"Policy Name: [cyan]{ingested.structure.policy_name}[/cyan]\n"
            f"Insurer: [cyan]{ingested.structure.insurer_name}[/cyan]\n"
            f"UIN: [cyan]{ingested.structure.uin}[/cyan]\n"
            f"Pages: {ingested.structure.page_count} | Parents: {len(ingested.parents)} | "
            f"Children: {len(ingested.children)} | Tables: {len(ingested.tables)}",
            title="Ingestion Summary",
        )
    )


def cmd_query(args: argparse.Namespace) -> None:
    pipeline = create_default_pipeline(use_stub=args.stub)
    settings = get_settings()

    # Ensure at least one policy is loaded
    if not pipeline.get_parent_index():
        sample_path = settings.raw_policies_dir / "arogya_sanjeevani_policy_wordings.pdf"
        if not sample_path.exists():
            create_arogya_sanjeevani_pdf(sample_path)
        pipeline.ingest_pdf(sample_path, doc_id="arogya_sanjeevani")

    resp = pipeline.query(args.question, doc_id=args.doc_id, top_k=args.top_k)

    console.print(Panel(f"[bold white]{resp.intent.redacted_query}[/bold white]", title="Query"))

    if resp.abstained:
        console.print(
            Panel(
                f"[bold red]{resp.answer}[/bold red]\n\nReason: {resp.abstention_reason}",
                title=f"ABSTENTION (Confidence: {resp.confidence_score * 100:.1f}%)",
                border_style="red",
            )
        )
        return

    # Formatted answer panel
    status_color = "green" if resp.confidence_score >= 0.70 else "yellow"
    console.print(
        Panel(
            f"{resp.answer}\n\n"
            f"[bold]Coverage Status:[/bold] {resp.coverage_summary.coverage_status}\n"
            f"[bold]Sub-limits:[/bold] {resp.coverage_summary.applicable_sub_limits}\n"
            f"[bold]Waiting Periods:[/bold] {resp.coverage_summary.waiting_period_details}\n"
            f"[bold]Co-Pay / Deductible:[/bold] {resp.coverage_summary.cost_sharing_or_deductible}",
            title=f"Grounded Answer (Confidence: {resp.confidence_score * 100:.1f}%)",
            border_style=status_color,
        )
    )

    # Citations table
    if resp.citations:
        tbl = Table(title="Grounded Citations")
        tbl.add_column("Ref", style="cyan")
        tbl.add_column("Section", style="magenta")
        tbl.add_column("Page", style="yellow")
        tbl.add_column("Verbatim Quote", style="white")

        for c in resp.citations:
            tbl.add_row(
                c.clause_code or c.citation_id,
                c.section_type.value,
                str(c.page_number),
                c.verbatim_quote[:100] + "...",
            )
        console.print(tbl)


def cmd_telemetry(_args: argparse.Namespace) -> None:
    pipeline = create_default_pipeline(use_stub=True)
    summary = pipeline.get_finops_summary()

    tbl = Table(title="FinOps Token & Cost Telemetry")
    tbl.add_column("Metric", style="cyan")
    tbl.add_column("Value", style="bold green")

    tbl.add_row("Total Cost (USD)", f"${summary.total_cost_usd:.5f}")
    tbl.add_row("Total Cost (INR)", f"₹{summary.total_cost_inr:.4f}")
    tbl.add_row("Total Model Calls", str(summary.total_calls))
    tbl.add_row("Cache Hits", str(summary.cache_hits))
    tbl.add_row("Cache Hit Ratio", f"{summary.cache_hit_ratio * 100:.1f}%")
    tbl.add_row("Prompt Tokens", str(summary.total_prompt_tokens))
    tbl.add_row("Completion Tokens", str(summary.total_completion_tokens))
    tbl.add_row("Embedding Tokens", str(summary.total_embedding_tokens))

    console.print(tbl)


def cmd_benchmark(_args: argparse.Namespace) -> None:
    pipeline = create_default_pipeline(use_stub=True)
    settings = get_settings()
    sample_path = settings.raw_policies_dir / "arogya_sanjeevani_policy_wordings.pdf"
    if not sample_path.exists():
        create_arogya_sanjeevani_pdf(sample_path)
    pipeline.ingest_pdf(sample_path, doc_id="arogya_sanjeevani")

    runner = BenchmarkRunner(pipeline)
    scorecard = runner.run_benchmark()

    tbl = Table(title="RAG Triad & IRDAI Benchmark Scorecard")
    tbl.add_column("Metric", style="cyan")
    tbl.add_column("Score", style="bold green")
    tbl.add_column("Threshold", style="yellow")
    tbl.add_column("Result", style="magenta")

    def add(m: str, s: float, t: float = 0.80) -> None:
        tbl.add_row(m, f"{s * 100:.1f}%", f"{t * 100:.1f}%", "PASS" if s >= t else "FAIL")

    add("Context Recall@K", scorecard.context_recall_at_k)
    add("Answer Faithfulness", scorecard.answer_faithfulness)
    add("Abstention F1 Score", scorecard.abstention_f1)
    add("Table Numerical Exactness", scorecard.table_numerical_exactness)

    console.print(tbl)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mmrag", description="Indian Insurance Multimodal RAG CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Ingest
    p_ingest = subparsers.add_parser("ingest", help="Ingest a policy PDF")
    p_ingest.add_argument("pdf_path", help="Path to PDF")
    p_ingest.add_argument("--doc-id", help="Optional document ID")
    p_ingest.add_argument(
        "--stub", action="store_true", default=True, help="Use deterministic stub model"
    )
    p_ingest.set_defaults(func=cmd_ingest)

    # Query
    p_query = subparsers.add_parser("query", help="Query policy with multimodal RAG")
    p_query.add_argument("question", help="Insurance question")
    p_query.add_argument("--doc-id", help="Optional doc_id")
    p_query.add_argument("--top-k", type=int, default=6, help="Top-K chunks")
    p_query.add_argument(
        "--stub", action="store_true", default=True, help="Use deterministic stub model"
    )
    p_query.set_defaults(func=cmd_query)

    # Telemetry
    p_tel = subparsers.add_parser("telemetry", help="View FinOps cost and token usage")
    p_tel.set_defaults(func=cmd_telemetry)

    # Benchmark
    p_bench = subparsers.add_parser("benchmark", help="Run RAG Triad benchmark evaluation")
    p_bench.set_defaults(func=cmd_benchmark)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
