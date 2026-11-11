"""Model Context Protocol (MCP) tool server exposure for enterprise agentic workflows."""

from __future__ import annotations

from typing import Any, cast

from insurance_mmrag.domain.irdai import IRDAI_STANDARD_EXCLUSIONS
from insurance_mmrag.evals.benchmark_runner import BenchmarkRunner
from insurance_mmrag.pipeline import InsuranceMMRAGPipeline
from insurance_mmrag.schemas import ApplicantProfile, SectionType


class MCPToolServer:
    """Exposes structured MCP-compatible tools for autonomous enterprise coding and claims agents."""

    def __init__(self, pipeline: InsuranceMMRAGPipeline) -> None:
        self.pipeline = pipeline

    def list_tools(self) -> list[dict[str, Any]]:
        """Return MCP-compliant tool declarations and input schemas."""
        return [
            {
                "name": "query_irdai_policy",
                "description": (
                    "Query an Indian health/motor insurance policy using multimodal RAG. "
                    "Returns grounded answer, confidence score, citations with page numbers, and abstention status."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The insurance coverage or claims question.",
                        },
                        "doc_id": {
                            "type": "string",
                            "description": "Optional policy document ID to scope search.",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "lookup_irdai_clause",
                "description": "Look up standardized IRDAI exclusion codes (Excl01 to Excl18) and their statutory definition.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "clause_code": {
                            "type": "string",
                            "description": "Standard code, e.g. 'Excl01' or 'Excl02'.",
                        },
                    },
                    "required": ["clause_code"],
                },
            },
            {
                "name": "inspect_policy_table",
                "description": "Retrieve structured Markdown and rows for a benefit schedule or CIS summary table.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "section_type": {
                            "type": "string",
                            "enum": [s.value for s in SectionType],
                            "description": "Target IRDAI section type.",
                        },
                    },
                    "required": ["section_type"],
                },
            },
            {
                "name": "get_rag_triad_scorecard",
                "description": "Run and return quantitative RAG Triad benchmark metrics (Recall@K, Faithfulness, Abstention F1, Table Exactness).",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "recommend_best_insurance_policy",
                "description": (
                    "Analyze an individual or family profile, generate follow-up probing questions, "
                    "evaluate Family Floater vs Parent-Split options, and rank eligible IRDAI policies with GST-inclusive premiums."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language description of applicant profile and family needs.",
                        },
                        "proposer_age": {"type": "integer", "description": "Age of proposer."},
                        "family_size": {"type": "integer", "description": "Total family members."},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "compare_insurance_policies",
                "description": (
                    "Compare multiple Indian health insurance policies side-by-side across 10 IRDAI clause-grounded parameters "
                    "with indicative premiums and hospital bill out-of-pocket simulation."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "doc_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of policy doc_ids to compare.",
                        },
                    },
                },
            },
        ]

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a declared MCP tool call and return JSON-serializable results."""
        if name == "query_irdai_policy":
            query_str = str(arguments.get("query", ""))
            doc_id = arguments.get("doc_id")
            resp = self.pipeline.query(user_query=query_str, doc_id=doc_id)
            return resp.model_dump(mode="json")

        if name == "lookup_irdai_clause":
            raw_code = str(arguments.get("clause_code", "")).strip()
            # Normalize to Excl01 format
            code_key = raw_code.replace("Code-", "").replace(" ", "").capitalize()
            if not code_key.startswith("Excl"):
                code_key = f"Excl{code_key}"

            title = IRDAI_STANDARD_EXCLUSIONS.get(code_key, "Unknown IRDAI Standard Code")
            # Look for matching parent in pipeline
            matches: list[dict[str, Any]] = []
            for pid, parent in self.pipeline.get_parent_index().items():
                if code_key in parent.clause_codes:
                    matches.append(
                        {
                            "parent_id": pid,
                            "section_type": parent.section_type.value,
                            "page_range": f"{parent.start_page}-{parent.end_page}",
                            "excerpt": parent.full_text[:300],
                        }
                    )
            return {
                "clause_code": code_key,
                "standard_title": title,
                "found_in_indexed_policy": bool(matches),
                "occurrences": matches,
            }

        if name == "inspect_policy_table":
            sec_type_str = str(arguments.get("section_type", ""))
            docs = self.pipeline.get_indexed_documents()
            matching_tables: list[dict[str, Any]] = []
            for doc in docs.values():
                for tbl in doc.tables:
                    if tbl.section_type.value == sec_type_str:
                        matching_tables.append(tbl.model_dump(mode="json"))
            return {"tables": matching_tables, "count": len(matching_tables)}

        if name == "get_rag_triad_scorecard":
            runner = BenchmarkRunner(self.pipeline)
            card = runner.run_benchmark()
            return card.model_dump(mode="json")

        if name == "recommend_best_insurance_policy":
            query_str = str(
                arguments.get(
                    "query",
                    "I am individual with age 26, non smoker and non drinker with family of 5 what is the best policy for me",
                )
            )
            prof: ApplicantProfile | None = None
            if "proposer_age" in arguments or "family_size" in arguments:
                prof = ApplicantProfile(
                    proposer_age=int(arguments.get("proposer_age", 26)),
                    family_size=int(arguments.get("family_size", 5)),
                )
            rec = self.pipeline.recommend_policies(user_query=query_str, profile=prof)
            return rec.model_dump(mode="json")

        if name == "compare_insurance_policies":
            raw_ids = arguments.get("doc_ids")
            doc_ids = (
                [str(x) for x in cast(list[object], raw_ids)] if isinstance(raw_ids, list) else None
            )
            comp = self.pipeline.compare_policies(doc_ids=doc_ids)
            return comp.model_dump(mode="json")

        return {"error": f"Tool '{name}' is not recognized."}
