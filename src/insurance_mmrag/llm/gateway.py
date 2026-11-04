"""Governed gateway: the ONLY path to a model.

Every generation and embedding call is forced through:
PII redaction -> prompt-injection sanitization -> budget circuit breaker -> SHA-256 cache
-> model call -> USD/INR cost record -> hash-chained audit entry.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import cast

from pydantic import BaseModel

from insurance_mmrag.llm.protocol import (
    EvidenceItem,
    GenerationRequest,
    ModelClient,
    Task,
    render_prompt,
)
from insurance_mmrag.schemas import CostTelemetryRecord
from insurance_mmrag.security.pii_redactor import PiiRedactor
from insurance_mmrag.security.sanitizer import PdfSanitizer
from insurance_mmrag.telemetry.audit_logger import AuditLogger
from insurance_mmrag.telemetry.cost_tracker import ContentCache, CostTracker, sha256_hex


def _empty_str_list() -> list[str]:
    return []


@dataclass
class GatewayResult[T: BaseModel]:
    parsed: T
    cost: CostTelemetryRecord
    pii_categories: list[str] = field(default_factory=_empty_str_list)
    injection_detected: bool = False


@dataclass
class EmbedOutcome:
    vectors: list[list[float]]
    cost: CostTelemetryRecord


class ModelGateway:
    def __init__(
        self,
        client: ModelClient,
        cost_tracker: CostTracker,
        audit_logger: AuditLogger,
        cache: ContentCache | None = None,
        redactor: PiiRedactor | None = None,
        sanitizer: PdfSanitizer | None = None,
    ) -> None:
        self.client = client
        self.cost_tracker = cost_tracker
        self.audit = audit_logger
        self.cache = cache
        self.redactor = redactor or PiiRedactor()
        self.sanitizer = sanitizer or PdfSanitizer()

    # ------------------------------------------------------------------ guards
    def guard_text(self, text: str) -> tuple[str, list[str], bool]:
        """Redact PII then neutralize injection payloads. Returns (clean, pii_categories, injected)."""
        red = self.redactor.redact(text)
        san = self.sanitizer.sanitize_text(red.redacted_text)
        return san.clean_text, list(red.categories), san.injection_detected

    # ------------------------------------------------------------------ generation
    def generate[T: BaseModel](
        self,
        *,
        task: Task,
        model: str,
        instruction: str,
        schema: type[T],
        operation: str,
        user_query: str = "",
        evidence: tuple[EvidenceItem, ...] = (),
        images: tuple[bytes, ...] = (),
        hints: dict[str, str] | None = None,
    ) -> GatewayResult[T]:
        pii: list[str] = []
        injected = False
        clean_query, cats, inj = self.guard_text(user_query)
        pii.extend(cats)
        injected |= inj
        clean_evidence: list[EvidenceItem] = []
        for item in evidence:
            text, cats, inj = self.guard_text(item.text)
            pii.extend(cats)
            injected |= inj
            clean_evidence.append(EvidenceItem(item.evidence_id, text))
        clean_hints: dict[str, str] = {}
        for key, value in (hints or {}).items():
            clean_hints[key] = self.guard_text(value)[0]

        request = GenerationRequest(
            task=task,
            model=model,
            instruction=instruction,
            response_schema=schema,
            user_query=clean_query,
            evidence=tuple(clean_evidence),
            images=images,
            hints=clean_hints,
        )
        image_digest = "".join(hashlib.sha256(img).hexdigest() for img in images)
        key = sha256_hex(model, task, schema.__name__, render_prompt(request), image_digest)
        unique_pii = sorted(set(pii))

        cached = self.cache.get(key) if self.cache else None
        if cached is not None:
            parsed = schema.model_validate(cached)
            cost = self.cost_tracker.record(operation, model, cache_hit=True)
            self._audit_call(operation, task, cost, unique_pii, injected)
            return GatewayResult(parsed, cost, unique_pii, injected)

        self.cost_tracker.check_budget()
        start = time.perf_counter()
        result = self.client.generate(request)
        latency = (time.perf_counter() - start) * 1000
        if not isinstance(result.parsed, schema):
            parsed = schema.model_validate(result.parsed.model_dump())
        else:
            parsed = result.parsed
        cost = self.cost_tracker.record(
            operation,
            result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            image_count=len(images),
            latency_ms=latency,
        )
        if self.cache:
            self.cache.put(key, parsed.model_dump(mode="json"))
        self._audit_call(operation, task, cost, unique_pii, injected)
        return GatewayResult(parsed, cost, unique_pii, injected)

    # ------------------------------------------------------------------ embeddings
    def embed(self, texts: list[str], *, model: str, dim: int, operation: str) -> EmbedOutcome:
        clean = [self.guard_text(t)[0] for t in texts]
        vectors: list[list[float] | None] = [None] * len(clean)
        misses: list[int] = []
        keys = [sha256_hex(model, str(dim), t) for t in clean]
        for i, key in enumerate(keys):
            cached = self.cache.get(key) if self.cache else None
            if isinstance(cached, list):
                vectors[i] = [float(v) for v in cast(list[float], cached)]
            else:
                misses.append(i)

        if not misses:
            cost = self.cost_tracker.record(operation, model, cache_hit=True)
        else:
            self.cost_tracker.check_budget()
            start = time.perf_counter()
            result = self.client.embed([clean[i] for i in misses], model, dim)
            latency = (time.perf_counter() - start) * 1000
            for idx, vec in zip(misses, result.vectors, strict=True):
                vectors[idx] = vec
                if self.cache:
                    self.cache.put(keys[idx], vec)
            cost = self.cost_tracker.record(
                operation, result.model, embedding_tokens=result.token_count, latency_ms=latency
            )
        self.audit.log(
            "MODEL_EMBED",
            {
                "operation": operation,
                "model": model,
                "texts": len(texts),
                "cache_misses": len(misses),
                "cost_usd": cost.cost_usd,
                "cost_inr": cost.cost_inr,
            },
        )
        return EmbedOutcome(vectors=[v for v in vectors if v is not None], cost=cost)

    def _audit_call(
        self,
        operation: str,
        task: str,
        cost: CostTelemetryRecord,
        pii: list[str],
        injected: bool,
    ) -> None:
        self.audit.log(
            "MODEL_CALL",
            {
                "operation": operation,
                "task": task,
                "model": cost.model_name,
                "prompt_tokens": cost.prompt_tokens,
                "completion_tokens": cost.completion_tokens,
                "image_count": cost.image_count,
                "cache_hit": cost.cache_hit,
                "cost_usd": cost.cost_usd,
                "cost_inr": cost.cost_inr,
                "pii_redacted": pii,
                "injection_neutralized": injected,
            },
        )
