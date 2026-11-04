"""Context assembler with bounded Corrective RAG (CRAG) and cross-reference expansion."""

from __future__ import annotations

from insurance_mmrag.domain.irdai import tokenize
from insurance_mmrag.indexing.multimodal_embedder import MultimodalEmbedder
from insurance_mmrag.indexing.vector_store import HybridVectorStore
from insurance_mmrag.ingestion.cross_ref_resolver import CrossReferenceResolver
from insurance_mmrag.schemas import (
    AssembledContext,
    CragHop,
    ParentChunk,
    QueryIntentClassification,
    RetrievedChunk,
)


class ContextAssembler:
    """Assembles full ParentChunks, resolves 1-hop cross-references, and executes CRAG."""

    def __init__(
        self,
        vector_store: HybridVectorStore,
        embedder: MultimodalEmbedder,
        cross_ref_resolver: CrossReferenceResolver | None = None,
        max_crag_hops: int = 2,
    ) -> None:
        self.vector_store = vector_store
        self.embedder = embedder
        self.cross_ref_resolver = cross_ref_resolver or CrossReferenceResolver()
        self.max_crag_hops = max_crag_hops

    def assemble_context(
        self,
        intent: QueryIntentClassification,
        parent_index: dict[str, ParentChunk],
        doc_id: str | None = None,
        top_k: int = 6,
    ) -> AssembledContext:
        # 1. Primary search
        q_vec, _ = self.embedder.embed_query(intent.redacted_query)
        retrieved = self.vector_store.hybrid_search(
            query=intent.redacted_query,
            query_vector=q_vec,
            doc_id=doc_id,
            target_sections=intent.target_sections,
            detected_clause_codes=intent.detected_clause_codes,
            boost_tables=intent.requires_table_boost,
            top_k=top_k,
        )

        retrieved_map: dict[str, RetrievedChunk] = {r.chunk.chunk_id: r for r in retrieved}
        crag_hops: list[CragHop] = []

        # 2. Bounded Corrective RAG (CRAG) for decomposed sub-queries
        sub_queries = [
            sq for sq in intent.sub_queries if sq.strip() != intent.redacted_query.strip()
        ]
        for hop_idx, sub_q in enumerate(sub_queries[: self.max_crag_hops]):
            sq_tokens = set(tokenize(sub_q))
            # Check coverage in existing retrieved text
            current_text = " ".join(r.chunk.text for r in retrieved_map.values())
            covered_tokens = sq_tokens.intersection(set(tokenize(current_text)))
            is_covered = len(covered_tokens) >= max(1, len(sq_tokens) // 2)

            if is_covered:
                crag_hops.append(
                    CragHop(
                        hop=hop_idx + 1,
                        sub_query=sub_q,
                        retrieved_chunk_ids=[],
                        covered=True,
                        reason="Sub-query concepts already covered in initial retrieved evidence.",
                    )
                )
            else:
                # Targeted follow-up retrieval hop
                sq_vec, _ = self.embedder.embed_query(sub_q)
                hop_hits = self.vector_store.hybrid_search(
                    query=sub_q,
                    query_vector=sq_vec,
                    doc_id=doc_id,
                    target_sections=intent.target_sections,
                    boost_tables=intent.requires_table_boost,
                    top_k=2,
                )
                new_cids: list[str] = []
                for h in hop_hits:
                    if h.chunk.chunk_id not in retrieved_map:
                        retrieved_map[h.chunk.chunk_id] = h
                        new_cids.append(h.chunk.chunk_id)

                crag_hops.append(
                    CragHop(
                        hop=hop_idx + 1,
                        sub_query=sub_q,
                        retrieved_chunk_ids=new_cids,
                        covered=bool(new_cids),
                        reason=f"Targeted CRAG hop added {len(new_cids)} missing clause chunk(s).",
                    )
                )

        final_retrieved = list(retrieved_map.values())
        final_retrieved.sort(key=lambda r: -r.normalized_score)

        # 3. Parent promotion: collect full ParentChunks
        cited_parent_ids = list(dict.fromkeys(r.chunk.metadata.parent_id for r in final_retrieved))
        parents: list[ParentChunk] = [
            parent_index[pid] for pid in cited_parent_ids if pid in parent_index
        ]

        # 4. 1-hop Cross-Reference Expansion
        xref_ids: list[str] = []
        for p in parents:
            for xpid in p.cross_references:
                if xpid in parent_index and xpid not in cited_parent_ids and xpid not in xref_ids:
                    xref_ids.append(xpid)
                    parents.append(parent_index[xpid])

        for r in final_retrieved:
            for xpid in r.chunk.metadata.cross_references:
                if xpid in parent_index and xpid not in cited_parent_ids and xpid not in xref_ids:
                    xref_ids.append(xpid)
                    parents.append(parent_index[xpid])

        # 5. IRDAI Precedence check
        precedence = self.cross_ref_resolver.check_precedence(cited_parent_ids, parent_index)

        # 6. Aggregate retrieval score
        avg_score = (
            sum(r.normalized_score for r in final_retrieved) / len(final_retrieved)
            if final_retrieved
            else 0.0
        )

        return AssembledContext(
            parents=parents,
            cross_referenced_parent_ids=xref_ids,
            retrieved=final_retrieved,
            crag_hops=crag_hops,
            precedence=precedence,
            retrieval_score=round(avg_score, 4),
        )
