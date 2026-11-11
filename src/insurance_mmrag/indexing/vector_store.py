"""Hybrid vector and lexical store: local Qdrant + BM25 with Reciprocal Rank Fusion (RRF)."""

from __future__ import annotations

from typing import Any, cast

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from rank_bm25 import BM25Okapi

from insurance_mmrag.domain.irdai import tokenize
from insurance_mmrag.schemas import (
    ChildChunk,
    ChunkType,
    RetrievedChunk,
    SectionType,
)

COLLECTION_NAME = "insurance_policy_chunks"


class HybridVectorStore:
    """Combines dense semantic search (Qdrant) with sparse lexical search (BM25) via RRF."""

    def __init__(self, location: str = ":memory:", dim: int = 768) -> None:
        self.location = location
        self.dim = dim
        self.client = QdrantClient(location=location)
        self._init_collection()
        self._chunks: dict[str, ChildChunk] = {}
        self._bm25: BM25Okapi | None = None
        self._chunk_ids_order: list[str] = []

    def _init_collection(self) -> None:
        collections = [c.name for c in self.client.get_collections().collections]
        if COLLECTION_NAME not in collections:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
            )

    def index_chunks(self, chunks: list[ChildChunk], vectors: list[list[float]]) -> int:
        """Upsert child chunks and their embeddings into Qdrant and rebuild BM25 index."""
        if not chunks:
            return 0

        points: list[PointStruct] = []
        tokenized_corpus: list[list[str]] = []

        for idx, (chunk, vec) in enumerate(zip(chunks, vectors, strict=True)):
            self._chunks[chunk.chunk_id] = chunk
            # Assign deterministic integer point id
            point_id = len(self._chunk_ids_order) + idx
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vec,
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text,
                        "doc_id": chunk.metadata.doc_id,
                        "section_type": chunk.metadata.section_type.value,
                        "chunk_type": chunk.metadata.chunk_type.value,
                        "clause_code": chunk.metadata.clause_code or "",
                        "parent_id": chunk.metadata.parent_id,
                        "page_number": chunk.metadata.page_number,
                    },
                )
            )

        self.client.upsert(collection_name=COLLECTION_NAME, points=points)

        # Update order & rebuild BM25 index over all indexed chunks
        self._chunk_ids_order.extend(c.chunk_id for c in chunks)
        tokenized_corpus = [tokenize(self._chunks[cid].text) for cid in self._chunk_ids_order]
        self._bm25 = BM25Okapi(tokenized_corpus)
        return len(chunks)

    def hybrid_search(
        self,
        query: str,
        query_vector: list[float],
        doc_id: str | None = None,
        target_sections: list[SectionType] | None = None,
        detected_clause_codes: list[str] | None = None,
        boost_tables: bool = False,
        top_k: int = 6,
        rrf_k: int = 60,
    ) -> list[RetrievedChunk]:
        """Execute hybrid search using Reciprocal Rank Fusion (RRF) with metadata pre-filters."""
        if not self._chunks:
            return []

        # 1. Build Qdrant pre-filter (filter by doc_id to ensure document isolation)
        conditions: list[FieldCondition] = []
        if doc_id:
            conditions.append(FieldCondition(key="doc_id", match=MatchValue(value=doc_id)))

        qdrant_filter = Filter(must=cast(list[Any], conditions)) if conditions else None

        # 2. Dense search via Qdrant
        dense_results = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=qdrant_filter,
            limit=top_k * 4,
        ).points

        dense_scores: dict[str, float] = {}
        for r in dense_results:
            payload: dict[str, Any] = r.payload or {}
            cid = str(payload.get("chunk_id", ""))
            if cid:
                dense_scores[cid] = float(r.score)

        # 3. Sparse BM25 search
        q_tokens = tokenize(query)
        bm25_scores: dict[str, float] = {}
        if self._bm25 and q_tokens:
            scores = list(self._bm25.get_scores(q_tokens))
            for cid, sc in zip(self._chunk_ids_order, scores, strict=True):
                chunk = self._chunks[cid]
                if doc_id and chunk.metadata.doc_id != doc_id:
                    continue
                if sc > 0.0:
                    bm25_scores[cid] = float(sc)

        # 4. Compute Reciprocal Rank Fusion (RRF)
        dense_ranked = sorted(dense_scores.keys(), key=lambda c: -dense_scores[c])
        bm25_ranked = sorted(bm25_scores.keys(), key=lambda c: -bm25_scores[c])

        all_candidates = set(dense_ranked) | set(bm25_ranked)
        if not all_candidates:
            # Fallback: take top dense matches without strict filter
            dense_unfiltered = self.client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                limit=top_k,
            ).points
            for r in dense_unfiltered:
                payload_unf: dict[str, Any] = r.payload or {}
                cid = str(payload_unf.get("chunk_id", ""))
                if cid:
                    all_candidates.add(cid)
                    dense_scores[cid] = float(r.score)
            dense_ranked = sorted(dense_scores.keys(), key=lambda c: -dense_scores[c])

        rrf_scores: dict[str, float] = {}
        clause_set = set(detected_clause_codes or [])
        target_section_set = set(target_sections or [])

        for cid in all_candidates:
            score = 0.0
            if cid in dense_ranked:
                rank_dense = dense_ranked.index(cid) + 1
                score += 1.0 / (rrf_k + rank_dense)
            if cid in bm25_ranked:
                rank_bm25 = bm25_ranked.index(cid) + 1
                score += 1.0 / (rrf_k + rank_bm25)

            chunk = self._chunks[cid]
            # Target Section Boost (+0.04) — prioritizes routed sections without blinding retrieval
            if target_section_set and chunk.metadata.section_type in target_section_set:
                score += 0.04

            # Exact clause code boost (e.g. Excl01 ranked #1)
            if chunk.metadata.clause_code and chunk.metadata.clause_code in clause_set:
                score += 0.05

            # Table boost for benefit/limit queries
            if boost_tables and chunk.metadata.chunk_type == ChunkType.TABLE:
                score += 0.02

            rrf_scores[cid] = score

        # Rank candidates by RRF score
        sorted_cids = sorted(all_candidates, key=lambda c: -rrf_scores[c])[:top_k]
        max_rrf = max(rrf_scores.values()) if rrf_scores else 1.0

        results: list[RetrievedChunk] = []
        for cid in sorted_cids:
            chunk = self._chunks[cid]
            raw_rrf = rrf_scores[cid]
            norm_score = min(1.0, max(0.0, raw_rrf / max_rrf))
            results.append(
                RetrievedChunk(
                    chunk=chunk,
                    dense_score=dense_scores.get(cid, 0.0),
                    bm25_score=bm25_scores.get(cid, 0.0),
                    rrf_score=round(raw_rrf, 6),
                    normalized_score=round(norm_score, 4),
                )
            )

        return results

    def get_chunk(self, chunk_id: str) -> ChildChunk | None:
        return self._chunks.get(chunk_id)

    def count(self) -> int:
        return len(self._chunks)
