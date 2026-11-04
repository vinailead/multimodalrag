"""Integration tests for FastAPI REST endpoints and Rich CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi.testclient import TestClient

from insurance_mmrag.api.main import app
from insurance_mmrag.cli import main as cli_main
from insurance_mmrag.ingestion.sample_policy_factory import create_arogya_sanjeevani_pdf


@pytest.fixture
def client() -> httpx.Client:
    return cast(httpx.Client, TestClient(app))


def test_api_health_endpoint(client: httpx.Client) -> None:
    resp: httpx.Response = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = cast(dict[str, Any], resp.json())
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"
    assert data["vector_store"] == "ready"
    assert data["indexed_policies_count"] >= 1


def test_api_list_policies(client: httpx.Client) -> None:
    resp: httpx.Response = client.get("/api/v1/policies")
    assert resp.status_code == 200
    policies = cast(list[dict[str, Any]], resp.json())
    assert len(policies) >= 1
    p = policies[0]
    assert "policy_name" in p
    assert "uin" in p
    assert int(p["page_count"]) >= 1


def test_api_query_endpoint(client: httpx.Client) -> None:
    # 1. Valid insurance question
    payload = {"query": "What is the cataract surgery waiting period?", "top_k": 4}
    resp: httpx.Response = client.post("/api/v1/query", json=payload)
    assert resp.status_code == 200
    data = cast(dict[str, Any], resp.json())
    assert "answer" in data
    assert float(data["confidence_score"]) >= 0.70
    assert data["abstained"] is False
    assert len(cast(list[Any], data["citations"])) >= 1
    assert "trace_spans" in data

    # 2. Out-of-scope question that triggers abstention
    payload_abstain = {"query": "Does this cover pet veterinary dental implants in Antarctica?"}
    resp_ab: httpx.Response = client.post("/api/v1/query", json=payload_abstain)
    assert resp_ab.status_code == 200
    data_ab = cast(dict[str, Any], resp_ab.json())
    assert data_ab["abstained"] is True
    assert "INDETERMINATE" in str(data_ab["answer"])


def test_api_telemetry_and_audit(client: httpx.Client) -> None:
    resp_cost: httpx.Response = client.get("/api/v1/telemetry/cost")
    assert resp_cost.status_code == 200
    data_cost = cast(dict[str, Any], resp_cost.json())
    assert "total_cost_usd" in data_cost
    assert "total_cost_inr" in data_cost
    assert float(data_cost["budget_usd"]) > 0

    resp_audit: httpx.Response = client.get("/api/v1/governance/audit?limit=10")
    assert resp_audit.status_code == 200
    audit_entries = cast(list[dict[str, Any]], resp_audit.json())
    assert isinstance(audit_entries, list)
    assert len(audit_entries) >= 1


def test_api_benchmark_scorecard(client: httpx.Client) -> None:
    resp: httpx.Response = client.get("/api/v1/benchmark/scorecard")
    assert resp.status_code == 200
    data = cast(dict[str, Any], resp.json())
    assert "context_recall_at_k" in data
    assert "answer_faithfulness" in data
    assert "abstention_f1" in data
    assert int(data["total_cases"]) >= 5


def test_api_mcp_endpoints(client: httpx.Client) -> None:
    resp_tools: httpx.Response = client.get("/api/v1/mcp/tools")
    assert resp_tools.status_code == 200
    tools = cast(list[dict[str, Any]], resp_tools.json())
    assert len(tools) >= 4

    resp_exec: httpx.Response = client.post(
        "/api/v1/mcp/execute",
        json={"tool_name": "lookup_irdai_clause", "arguments": {"clause_code": "Excl01"}},
    )
    assert resp_exec.status_code == 200
    result = cast(dict[str, Any], resp_exec.json())
    assert result["clause_code"] == "Excl01"
    assert "Pre-Existing Diseases" in str(result["standard_title"])


def test_api_crop_not_found(client: httpx.Client) -> None:
    resp: httpx.Response = client.get("/api/v1/crops/non_existent_crop.png")
    assert resp.status_code == 404


def test_cli_commands(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pdf_path = create_arogya_sanjeevani_pdf(tmp_path / "arogya.pdf")

    # Ingest
    monkeypatch.setattr("sys.argv", ["mmrag", "ingest", str(pdf_path), "--stub"])
    cli_main()

    # Query
    monkeypatch.setattr(
        "sys.argv",
        ["mmrag", "query", "What is the waiting period for cataract?", "--stub"],
    )
    cli_main()

    # Telemetry
    monkeypatch.setattr("sys.argv", ["mmrag", "telemetry"])
    cli_main()

    # Benchmark
    monkeypatch.setattr("sys.argv", ["mmrag", "benchmark"])
    cli_main()
