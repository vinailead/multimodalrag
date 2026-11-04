"""USD/INR token cost accounting, budget circuit breaker and SHA-256 content cache."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from insurance_mmrag.schemas import CostTelemetryRecord, FinOpsSummary


@dataclass(frozen=True)
class ModelPrice:
    input_per_million_usd: float
    output_per_million_usd: float


# Published Gemini list prices (USD per 1M tokens). Image inputs are billed as 258 tokens each.
PRICING: dict[str, ModelPrice] = {
    "gemini-2.5-flash": ModelPrice(0.15, 0.60),
    "gemini-2.5-pro": ModelPrice(1.25, 10.00),
    "gemini-embedding-001": ModelPrice(0.025, 0.0),
    "gemini-embedding-2-preview": ModelPrice(0.025, 0.0),
    "stub-gemini": ModelPrice(0.15, 0.60),
}
IMAGE_TOKENS = 258


class BudgetExceededError(RuntimeError):
    """Raised before a paid call when the configured spend ceiling has been reached."""


def sha256_hex(*parts: str | bytes) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8") if isinstance(part, str) else part)
        digest.update(b"\x1f")
    return digest.hexdigest()


class CostTracker:
    """Thread-safe accumulator of every model call's tokens and cost."""

    def __init__(self, usd_to_inr: float = 84.0, budget_usd: float = 5.0) -> None:
        self.usd_to_inr = usd_to_inr
        self.budget_usd = budget_usd
        self._records: list[CostTelemetryRecord] = []
        self._lock = threading.Lock()

    @staticmethod
    def price_for(model_name: str) -> ModelPrice:
        return PRICING.get(model_name, PRICING["gemini-2.5-flash"])

    def compute_cost_usd(
        self,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        embedding_tokens: int = 0,
        image_count: int = 0,
    ) -> float:
        price = self.price_for(model_name)
        input_tokens = prompt_tokens + embedding_tokens + image_count * IMAGE_TOKENS
        return (
            input_tokens * price.input_per_million_usd
            + completion_tokens * price.output_per_million_usd
        ) / 1_000_000

    @property
    def total_usd(self) -> float:
        with self._lock:
            return sum(r.cost_usd for r in self._records)

    def check_budget(self) -> None:
        if self.total_usd >= self.budget_usd:
            raise BudgetExceededError(
                f"FinOps circuit breaker tripped: spent ${self.total_usd:.4f} "
                f">= budget ${self.budget_usd:.2f}."
            )

    def record(
        self,
        operation: str,
        model_name: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        embedding_tokens: int = 0,
        image_count: int = 0,
        cache_hit: bool = False,
        latency_ms: float = 0.0,
    ) -> CostTelemetryRecord:
        usd = (
            0.0
            if cache_hit
            else self.compute_cost_usd(
                model_name, prompt_tokens, completion_tokens, embedding_tokens, image_count
            )
        )
        rec = CostTelemetryRecord(
            operation=operation,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            embedding_tokens=embedding_tokens,
            image_count=image_count,
            cache_hit=cache_hit,
            cost_usd=round(usd, 8),
            cost_inr=round(usd * self.usd_to_inr, 8),
            latency_ms=round(latency_ms, 3),
        )
        with self._lock:
            self._records.append(rec)
        return rec

    def records(self) -> list[CostTelemetryRecord]:
        with self._lock:
            return list(self._records)

    @staticmethod
    def merge(operation: str, records: list[CostTelemetryRecord]) -> CostTelemetryRecord:
        """Aggregate a set of records (e.g. one query) into a single telemetry line."""
        usd = sum(r.cost_usd for r in records)
        inr = sum(r.cost_inr for r in records)
        models = sorted({r.model_name for r in records})
        return CostTelemetryRecord(
            operation=operation,
            model_name="+".join(models) if models else "none",
            prompt_tokens=sum(r.prompt_tokens for r in records),
            completion_tokens=sum(r.completion_tokens for r in records),
            embedding_tokens=sum(r.embedding_tokens for r in records),
            image_count=sum(r.image_count for r in records),
            cache_hit=bool(records) and all(r.cache_hit for r in records),
            cost_usd=round(usd, 8),
            cost_inr=round(inr, 8),
            latency_ms=round(sum(r.latency_ms for r in records), 3),
        )

    def summary(self) -> FinOpsSummary:
        recs = self.records()
        per_model: dict[str, float] = defaultdict(float)
        for r in recs:
            per_model[r.model_name] += r.cost_usd
        total = sum(r.cost_usd for r in recs)
        hits = sum(1 for r in recs if r.cache_hit)
        return FinOpsSummary(
            total_cost_usd=round(total, 8),
            total_cost_inr=round(total * self.usd_to_inr, 6),
            total_calls=len(recs),
            cache_hits=hits,
            cache_hit_ratio=round(hits / len(recs), 4) if recs else 0.0,
            budget_usd=self.budget_usd,
            budget_remaining_usd=round(max(self.budget_usd - total, 0.0), 8),
            per_model_usd={k: round(v, 8) for k, v in per_model.items()},
            total_prompt_tokens=sum(r.prompt_tokens for r in recs),
            total_completion_tokens=sum(r.completion_tokens for r in recs),
            total_embedding_tokens=sum(r.embedding_tokens for r in recs),
        )


class ContentCache:
    """Content-addressable JSON disk cache keyed by SHA-256 (zero cost on repeat work)."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not all(c in "0123456789abcdef" for c in key) or len(key) != 64:
            raise ValueError("Cache key must be a SHA-256 hex digest.")
        return self.root / f"{key}.json"

    def get(self, key: str) -> object | None:
        path = self._path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def put(self, key: str, value: object) -> None:
        self._path(key).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
