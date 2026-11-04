"""Quantitative RAG Triad and IRDAI Regulatory Benchmark Scorecard Evaluator."""

from __future__ import annotations

import re

from insurance_mmrag.pipeline import InsuranceMMRAGPipeline
from insurance_mmrag.schemas import (
    BenchmarkCaseResult,
    GoldenExample,
    RAGTriadScorecard,
    SectionType,
)

GOLDEN_BENCHMARK_CASES: list[GoldenExample] = [
    GoldenExample(
        question="What is the waiting period for Pre-Existing Diseases under Code-Excl01?",
        expected_clause_codes=["Excl01"],
        expected_sections=[SectionType.WAITING_PERIODS, SectionType.EXCLUSIONS],
        expected_numbers=["48"],
        should_abstain=False,
    ),
    GoldenExample(
        question="What is the maximum limit for cataract surgery per eye?",
        expected_clause_codes=["Excl02"],
        expected_sections=[SectionType.SCHEDULE_OF_BENEFITS, SectionType.WAITING_PERIODS],
        expected_numbers=["40,000"],
        should_abstain=False,
    ),
    GoldenExample(
        question="What is the daily room rent sub-limit and mandatory co-payment percentage?",
        expected_clause_codes=[],
        expected_sections=[SectionType.SCHEDULE_OF_BENEFITS, SectionType.COST_SHARING],
        expected_numbers=["2%", "5%"],
        should_abstain=False,
    ),
    GoldenExample(
        question="Are AYUSH in-patient treatments covered, and up to what limit?",
        expected_clause_codes=[],
        expected_sections=[SectionType.BASE_COVERAGE, SectionType.DEFINITIONS],
        expected_numbers=["100%"],
        should_abstain=False,
    ),
    GoldenExample(
        question="Does this policy cover cosmetic surgery for beautification under Code-Excl08?",
        expected_clause_codes=["Excl08"],
        expected_sections=[SectionType.EXCLUSIONS],
        expected_numbers=[],
        should_abstain=False,
    ),
    # Adversarial / Out-of-scope traps that MUST deterministically abstain (< 0.70)
    GoldenExample(
        question="Does this insurance policy cover pet veterinary dental implants in Antarctica?",
        expected_clause_codes=[],
        expected_sections=[],
        expected_numbers=[],
        should_abstain=True,
    ),
    GoldenExample(
        question="What is the reimbursement limit for interstellar spaceship damage?",
        expected_clause_codes=[],
        expected_sections=[],
        expected_numbers=[],
        should_abstain=True,
    ),
]


class BenchmarkRunner:
    """Evaluates the pipeline on Golden IRDAI Benchmark cases and generates a RAG Triad Scorecard."""

    def __init__(self, pipeline: InsuranceMMRAGPipeline) -> None:
        self.pipeline = pipeline

    def run_benchmark(self, cases: list[GoldenExample] | None = None) -> RAGTriadScorecard:
        test_cases = cases or GOLDEN_BENCHMARK_CASES
        results: list[BenchmarkCaseResult] = []

        total_recall = 0.0
        total_faithfulness = 0.0
        total_table_exact = 0.0
        table_count = 0

        true_abstain = 0
        false_abstain = 0
        true_answer = 0
        false_answer = 0

        for case in test_cases:
            resp = self.pipeline.query(case.question)

            # 1. Abstention check
            if case.should_abstain:
                if resp.abstained:
                    true_abstain += 1
                else:
                    false_answer += 1
            else:
                if resp.abstained:
                    false_abstain += 1
                else:
                    true_answer += 1

            # 2. Context recall check
            recall = 1.0
            if not case.should_abstain:
                retrieved_text = " ".join(
                    f"{c.verbatim_quote} {c.parent_context_preview}" for c in resp.citations
                )
                retrieved_sections = {c.section_type for c in resp.citations}

                code_needed = len(case.expected_clause_codes)
                code_hits = sum(
                    1
                    for code in case.expected_clause_codes
                    if code in retrieved_text or any(c.clause_code == code for c in resp.citations)
                )

                sec_needed = 1 if case.expected_sections else 0
                sec_hits = (
                    1 if any(sec in retrieved_sections for sec in case.expected_sections) else 0
                )

                needed = code_needed + sec_needed
                hits = code_hits + sec_hits
                recall = hits / needed if needed > 0 else 1.0
                total_recall += recall

            # 3. Faithfulness check
            faithfulness = 1.0
            if not resp.abstained:
                faithfulness = resp.confidence_score
                total_faithfulness += faithfulness

            # 4. Numerical exactness check
            exact: float | None = None
            if case.expected_numbers and not resp.abstained:
                ans_text_norm = re.sub(r"[\s,₹·]", "", resp.answer.lower())
                num_hits = 0
                for num in case.expected_numbers:
                    num_norm = re.sub(r"[\s,₹·]", "", num.lower())
                    if num_norm in ans_text_norm:
                        num_hits += 1
                exact = num_hits / len(case.expected_numbers)
                total_table_exact += exact
                table_count += 1

            results.append(
                BenchmarkCaseResult(
                    question=case.question,
                    context_recall=round(recall, 3),
                    faithfulness=round(faithfulness, 3),
                    abstained=resp.abstained,
                    should_abstain=case.should_abstain,
                    table_exact=round(exact, 3) if exact is not None else None,
                    confidence=round(resp.confidence_score, 3),
                )
            )

        answered_cases = max(1, len(test_cases) - sum(1 for c in test_cases if c.should_abstain))
        avg_recall = total_recall / answered_cases
        avg_faith = total_faithfulness / answered_cases
        avg_exact = total_table_exact / max(1, table_count)

        # Abstention F1
        denom = 2 * true_abstain + false_answer + false_abstain
        abstain_f1 = (2 * true_abstain) / denom if denom > 0 else 1.0

        finops = self.pipeline.get_finops_summary()

        return RAGTriadScorecard(
            context_recall_at_k=round(avg_recall, 4),
            answer_faithfulness=round(avg_faith, 4),
            abstention_f1=round(abstain_f1, 4),
            table_numerical_exactness=round(avg_exact, 4),
            total_cases=len(test_cases),
            total_cost_usd=finops.total_cost_usd,
            cases=results,
        )
