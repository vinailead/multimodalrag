"""Multimodal embedder using Gemini Embeddings with content caching and L2 normalization."""

from __future__ import annotations

import math

from insurance_mmrag.llm.gateway import ModelGateway
from insurance_mmrag.schemas import CostTelemetryRecord


def l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


class MultimodalEmbedder:
    """Generates normalized vector embeddings for chunks and queries via ModelGateway."""

    def __init__(
        self,
        gateway: ModelGateway,
        model: str = "gemini-embedding-001",
        dim: int = 768,
    ) -> None:
        self.gateway = gateway
        self.model = model
        self.dim = dim

    def embed_texts(
        self, texts: list[str], operation: str = "indexing.embed_chunks"
    ) -> tuple[list[list[float]], CostTelemetryRecord]:
        """Embed a batch of texts, returning normalized vectors and telemetry."""
        if not texts:
            empty_cost = self.gateway.cost_tracker.record(operation, self.model, cache_hit=True)
            return [], empty_cost

        outcome = self.gateway.embed(
            texts=texts,
            model=self.model,
            dim=self.dim,
            operation=operation,
        )
        normalized = [l2_normalize(v) for v in outcome.vectors]
        return normalized, outcome.cost

    def embed_query(
        self, query: str, operation: str = "retrieval.embed_query"
    ) -> tuple[list[float], CostTelemetryRecord]:
        """Embed a single search query."""
        vecs, cost = self.embed_texts([query], operation=operation)
        if not vecs:
            return [0.0] * self.dim, cost
        return vecs[0], cost
