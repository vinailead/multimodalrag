"""Unit and integration tests for Model Context Protocol (MCP) tools and RAG Triad benchmark."""

from __future__ import annotations

from pathlib import Path

import pytest

from insurance_mmrag.config import Settings
from insurance_mmrag.evals.benchmark_runner import BenchmarkRunner
from insurance_mmrag.indexing.vector_store import HybridVectorStore
from insurance_mmrag.ingestion.sample_policy_factory import create_arogya_sanjeevani_pdf
from insurance_mmrag.llm.gateway import ModelGateway
from insurance_mmrag.mcp_tools import MCPToolServer
from insurance_mmrag.pipeline import InsuranceMMRAGPipeline


@pytest.fixture
def pipeline_with_doc(gateway: ModelGateway, tmp_path: Path) -> InsuranceMMRAGPipeline:
    settings = Settings(
        data_dir=tmp_path / "data",
        logs_dir=tmp_path / "logs",
        use_stub_model=True,
    )
    store = HybridVectorStore(dim=768)
    pipe = InsuranceMMRAGPipeline(gateway=gateway, settings=settings, vector_store=store)

    pdf_path = create_arogya_sanjeevani_pdf(tmp_path / "arogya.pdf")
    pipe.ingest_pdf(pdf_path, doc_id="arogya_sanjeevani")
    return pipe


def test_mcp_tool_server_lifecycle(pipeline_with_doc: InsuranceMMRAGPipeline) -> None:
    server = MCPToolServer(pipeline_with_doc)

    # 1. List tools
    tools = server.list_tools()
    assert len(tools) == 6
    tool_names = [t["name"] for t in tools]
    assert "query_irdai_policy" in tool_names
    assert "lookup_irdai_clause" in tool_names
    assert "inspect_policy_table" in tool_names
    assert "get_rag_triad_scorecard" in tool_names
    assert "recommend_best_insurance_policy" in tool_names
    assert "compare_insurance_policies" in tool_names

    # 2. Execute query_irdai_policy
    q_res = server.execute_tool("query_irdai_policy", {"query": "What is the cataract sub-limit?"})
    assert "answer" in q_res
    assert "confidence_score" in q_res
    assert q_res["abstained"] is False

    # 3. Execute lookup_irdai_clause
    clause_res = server.execute_tool("lookup_irdai_clause", {"clause_code": "Excl01"})
    assert clause_res["clause_code"] == "Excl01"
    assert "Pre-Existing Diseases" in clause_res["standard_title"]
    assert clause_res["found_in_indexed_policy"] is True

    # 4. Execute inspect_policy_table
    table_res = server.execute_tool(
        "inspect_policy_table", {"section_type": "Schedule_of_Benefits"}
    )
    assert table_res["count"] >= 1
    assert "markdown_table" in table_res["tables"][0]

    # 5. Unknown tool handles cleanly
    err = server.execute_tool("non_existent_tool", {})
    assert "error" in err


def test_rag_triad_benchmark_scorecard(pipeline_with_doc: InsuranceMMRAGPipeline) -> None:
    runner = BenchmarkRunner(pipeline_with_doc)
    card = runner.run_benchmark()

    assert card.total_cases >= 5
    assert card.context_recall_at_k >= 0.80
    assert card.answer_faithfulness >= 0.70
    assert card.abstention_f1 >= 0.80
    assert card.table_numerical_exactness >= 0.75
