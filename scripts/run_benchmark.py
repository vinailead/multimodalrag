"""CLI runner for quantitative RAG Triad & IRDAI benchmark evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from rich.table import Table

from insurance_mmrag.evals.benchmark_runner import BenchmarkRunner
from insurance_mmrag.ingestion.sample_policy_factory import create_arogya_sanjeevani_pdf
from insurance_mmrag.pipeline import create_default_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAG Triad benchmark evaluation.")
    parser.add_argument("--pdf-path", help="Path to policy PDF (default generates sample)")
    args = parser.parse_args()

    console = Console()
    console.print("[bold blue]Starting IRDAI Multimodal RAG Benchmark Evaluation...[/bold blue]")

    pipeline = create_default_pipeline(use_stub=True)
    if args.pdf_path:
        pdf_path = Path(args.pdf_path)
    else:
        pdf_path = Path("data/raw_policies/arogya_sanjeevani_policy_wordings.pdf")
        if not pdf_path.exists():
            create_arogya_sanjeevani_pdf(pdf_path)

    pipeline.ingest_pdf(pdf_path, doc_id="arogya_sanjeevani")
    runner = BenchmarkRunner(pipeline)
    scorecard = runner.run_benchmark()

    table = Table(title="IRDAI Multimodal RAG Triad Benchmark Scorecard")
    table.add_column("Metric", style="cyan")
    table.add_column("Score", style="bold green")
    table.add_column("Target Threshold", style="yellow")
    table.add_column("Status", style="magenta")

    def row(name: str, score: float, target: float = 0.80) -> None:
        status = "PASSED (>=80%)" if score >= target else "FAILED"
        table.add_row(name, f"{score * 100:.1f}%", f"{target * 100:.1f}%", status)

    row("Context Recall@K", scorecard.context_recall_at_k)
    row("Answer Faithfulness", scorecard.answer_faithfulness)
    row("Abstention F1 Score", scorecard.abstention_f1)
    row("Table Numerical Exactness", scorecard.table_numerical_exactness)

    console.print(table)
    console.print(
        f"\n[green]Evaluated {scorecard.total_cases} cases at total cost ${scorecard.total_cost_usd:.4f}[/green]"
    )


if __name__ == "__main__":
    main()
