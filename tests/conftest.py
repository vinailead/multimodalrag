"""Shared fixtures. Every model interaction uses StubGeminiClient — never a live model."""

from __future__ import annotations

from pathlib import Path

import pytest

from insurance_mmrag.llm.gateway import ModelGateway
from insurance_mmrag.telemetry.audit_logger import AuditLogger
from insurance_mmrag.telemetry.cost_tracker import ContentCache, CostTracker
from insurance_mmrag.testing.stub_gemini import StubGeminiClient


@pytest.fixture
def stub_client() -> StubGeminiClient:
    return StubGeminiClient()


@pytest.fixture
def cost_tracker() -> CostTracker:
    return CostTracker(usd_to_inr=84.0, budget_usd=5.0)


@pytest.fixture
def audit_logger(tmp_path: Path) -> AuditLogger:
    return AuditLogger(tmp_path / "logs" / "audit_trail.jsonl")


@pytest.fixture
def gateway(
    tmp_path: Path,
    stub_client: StubGeminiClient,
    cost_tracker: CostTracker,
    audit_logger: AuditLogger,
) -> ModelGateway:
    return ModelGateway(
        client=stub_client,
        cost_tracker=cost_tracker,
        audit_logger=audit_logger,
        cache=ContentCache(tmp_path / "cache" / "llm"),
    )
