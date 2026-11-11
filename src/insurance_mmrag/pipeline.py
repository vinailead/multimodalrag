"""Master pipeline orchestrator wiring security, ingestion, indexing, retrieval, generation, and telemetry."""

from __future__ import annotations

from pathlib import Path

from insurance_mmrag.advisor.claim_simulator import ClaimSimulator
from insurance_mmrag.advisor.policy_comparator import PolicyComparator
from insurance_mmrag.advisor.recommendation_engine import (
    RecommendationEngine,
    is_advisory_or_comparison_query,
)
from insurance_mmrag.config import Settings, get_settings
from insurance_mmrag.generation.grounded_generator import GroundedGenerator
from insurance_mmrag.indexing.multimodal_embedder import MultimodalEmbedder
from insurance_mmrag.indexing.vector_store import HybridVectorStore
from insurance_mmrag.ingestion.parent_child_chunker import ParentChildChunker
from insurance_mmrag.ingestion.pdf_loader import PdfLoader
from insurance_mmrag.ingestion.structure_analyzer import StructureAnalyzer
from insurance_mmrag.ingestion.table_vision_parser import TableVisionParser
from insurance_mmrag.llm.gateway import ModelGateway
from insurance_mmrag.llm.gemini_client import GeminiClient
from insurance_mmrag.retrieval.context_assembler import ContextAssembler
from insurance_mmrag.retrieval.intent_router import IntentRouter
from insurance_mmrag.schemas import (
    AdvisorRecommendationResponse,
    ApplicantProfile,
    ClaimSimulationResponse,
    FinOpsSummary,
    GroundedQueryResponse,
    IngestedDocument,
    ParentChunk,
    PolicyComparisonResponse,
    PolicyCoverageSummary,
)
from insurance_mmrag.security.pii_redactor import PiiRedactor
from insurance_mmrag.security.sanitizer import PdfSanitizer
from insurance_mmrag.telemetry.audit_logger import AuditLogger
from insurance_mmrag.telemetry.cost_tracker import ContentCache, CostTracker
from insurance_mmrag.telemetry.trace_recorder import TraceRecorder
from insurance_mmrag.testing.stub_gemini import StubGeminiClient


class InsuranceMMRAGPipeline:
    """Enterprise Multimodal RAG pipeline for Indian Insurance policies."""

    def __init__(
        self,
        gateway: ModelGateway,
        settings: Settings,
        vector_store: HybridVectorStore | None = None,
    ) -> None:
        self.gateway = gateway
        self.settings = settings
        self.vector_store = vector_store or HybridVectorStore(dim=settings.embedding_dim)

        self.pdf_loader = PdfLoader(sanitizer=gateway.sanitizer)
        self.structure_analyzer = StructureAnalyzer(gateway=gateway, model=settings.flash_model)
        self.table_parser = TableVisionParser(
            gateway=gateway,
            crops_dir=settings.crops_dir,
            cache_dir=settings.cache_dir,
            model=settings.flash_model,
        )
        self.chunker = ParentChildChunker(table_parser=self.table_parser)
        self.embedder = MultimodalEmbedder(
            gateway=gateway, model=settings.embedding_model, dim=settings.embedding_dim
        )
        self.intent_router = IntentRouter(
            gateway=gateway, model=settings.flash_model, max_sub_queries=settings.max_sub_queries
        )
        self.context_assembler = ContextAssembler(
            vector_store=self.vector_store,
            embedder=self.embedder,
            max_crag_hops=settings.max_crag_hops,
        )
        self.generator = GroundedGenerator(
            gateway=gateway,
            flash_model=settings.flash_model,
            pro_model=settings.pro_model,
            min_confidence_threshold=settings.min_confidence_threshold,
        )
        self.recommendation_engine = RecommendationEngine()
        self.policy_comparator = PolicyComparator()
        self.claim_simulator = ClaimSimulator()

        self._parent_index: dict[str, ParentChunk] = {}
        self._indexed_docs: dict[str, IngestedDocument] = {}

    def ingest_pdf(self, pdf_path: Path, doc_id: str | None = None) -> IngestedDocument:
        assigned_id = doc_id or pdf_path.stem
        _, pages = self.pdf_loader.load(pdf_path)
        structure = self.structure_analyzer.analyze(pages, doc_id=assigned_id)
        ingested = self.chunker.chunk_document(structure, pages)

        # Embed child chunks and upsert to vector store
        texts = [c.text for c in ingested.children]
        vectors, _ = self.embedder.embed_texts(texts, operation=f"ingest.{assigned_id}.embed")
        self.vector_store.index_chunks(ingested.children, vectors)

        for p in ingested.parents:
            self._parent_index[p.parent_id] = p
        self._indexed_docs[assigned_id] = ingested

        self.gateway.audit.log(
            "POLICY_INGESTED",
            {
                "doc_id": assigned_id,
                "policy_name": structure.policy_name,
                "uin": structure.uin,
                "page_count": structure.page_count,
                "parents_count": len(ingested.parents),
                "children_count": len(ingested.children),
                "tables_count": len(ingested.tables),
            },
        )
        return ingested

    def query(
        self,
        user_query: str,
        doc_id: str | None = None,
        top_k: int = 6,
    ) -> GroundedQueryResponse:
        trace = TraceRecorder()

        with trace.span("pipeline.query", original_query=user_query):
            # Step 1: Intent Routing & CRAG Decomposition
            with trace.span("retrieval.intent_route"):
                intent = self.intent_router.classify_intent(user_query)

            # Step 2: Hybrid Search & Bounded CRAG Context Assembly
            with trace.span("retrieval.context_assembly", hops=len(intent.sub_queries)):
                context = self.context_assembler.assemble_context(
                    intent=intent,
                    parent_index=self._parent_index,
                    doc_id=doc_id,
                    top_k=top_k,
                )

            # Step 3: Grounded Synthesis & Citation Verification
            with trace.span("generation.grounded_synthesis"):
                response = self.generator.generate_response(
                    intent=intent,
                    context=context,
                    trace=trace,
                )

            # Step 4: Advisory & Comparison Enrichment when user asks for best policy / comparison
            if is_advisory_or_comparison_query(user_query):
                with trace.span("advisor.recommendation_enrichment"):
                    adv_rec = self.recommendation_engine.recommend(intent.redacted_query)
                    top_card = adv_rec.ranked_policies[0].feature_card
                    top_prem = adv_rec.ranked_policies[0].premium
                    response = response.model_copy(
                        update={
                            "answer": adv_rec.executive_advisory_summary,
                            "confidence_score": max(response.confidence_score, 0.92),
                            "abstained": False,
                            "abstention_reason": None,
                            "coverage_summary": PolicyCoverageSummary(
                                coverage_status="COVERED",
                                waiting_period_details=f"{top_card.ped_waiting_months} months PED (Excl01); {top_card.specific_disease_waiting_months} months Specific (Excl02)",
                                applicable_sub_limits=f"{top_card.room_rent_limit} | Annual Premium: ₹{top_prem.total_annual_premium_inr:,}/yr",
                                cost_sharing_or_deductible=f"{top_card.mandatory_copay_pct:.0f}% Mandatory Co-Pay",
                                applicable_exclusions=["Excl01", "Excl02"],
                            ),
                            "advisor_recommendation": adv_rec,
                        }
                    )

        response = response.model_copy(update={"trace_spans": trace.spans()})

        self.gateway.audit.log(
            "POLICY_QUERY_COMPLETED",
            {
                "query_id": response.query_id,
                "redacted_query": response.intent.redacted_query,
                "confidence_score": response.confidence_score,
                "abstained": response.abstained,
                "citations_count": len(response.citations),
                "model_used": response.model_used,
                "has_advisor_recommendation": response.advisor_recommendation is not None,
            },
        )
        return response

    def recommend_policies(
        self,
        user_query: str,
        profile: ApplicantProfile | None = None,
    ) -> AdvisorRecommendationResponse:
        clean_query, pii_cats, _ = self.gateway.guard_text(user_query)
        result = self.recommendation_engine.recommend(clean_query, explicit_profile=profile)
        self.gateway.audit.log(
            "ADVISOR_RECOMMENDATION_COMPLETED",
            {
                "redacted_query": clean_query,
                "pii_redacted": pii_cats,
                "proposer_age": result.extracted_profile.proposer_age,
                "family_size": result.extracted_profile.family_size,
                "needs_probing": result.needs_probing,
                "top_policy": result.ranked_policies[0].feature_card.doc_id,
                "top_annual_premium_inr": result.ranked_policies[
                    0
                ].premium.total_annual_premium_inr,
            },
        )
        return result

    def compare_policies(
        self,
        doc_ids: list[str] | None = None,
        profile: ApplicantProfile | None = None,
    ) -> PolicyComparisonResponse:
        result = self.policy_comparator.compare(doc_ids=doc_ids, profile=profile)
        self.gateway.audit.log(
            "POLICY_COMPARISON_COMPLETED",
            {
                "compared_doc_ids": [c.doc_id for c in result.compared_policies],
                "family_size": result.profile_used.family_size,
                "sum_insured_inr": result.profile_used.target_sum_insured_inr,
            },
        )
        return result

    def simulate_claim(
        self,
        claimed_bill_inr: int = 150_000,
        hospital_room_rent_per_day_inr: int = 8_000,
        days_hospitalized: int = 3,
        procedure_type: str = "general_hospitalization",
        sum_insured_inr: int = 1_000_000,
        doc_ids: list[str] | None = None,
    ) -> ClaimSimulationResponse:
        return self.claim_simulator.simulate(
            claimed_bill_inr=claimed_bill_inr,
            hospital_room_rent_per_day_inr=hospital_room_rent_per_day_inr,
            days_hospitalized=days_hospitalized,
            procedure_type=procedure_type,
            sum_insured_inr=sum_insured_inr,
            doc_ids=doc_ids,
        )

    def get_parent_index(self) -> dict[str, ParentChunk]:
        return dict(self._parent_index)

    def get_indexed_documents(self) -> dict[str, IngestedDocument]:
        return dict(self._indexed_docs)

    def get_finops_summary(self) -> FinOpsSummary:
        return self.gateway.cost_tracker.summary()


def create_default_pipeline(
    settings: Settings | None = None,
    use_stub: bool = True,
    api_key: str | None = None,
) -> InsuranceMMRAGPipeline:
    cfg = settings or get_settings()
    cost_tracker = CostTracker(usd_to_inr=cfg.usd_to_inr_rate, budget_usd=cfg.max_daily_budget_usd)
    audit_logger = AuditLogger(path=cfg.audit_log_path)
    cache = ContentCache(root=cfg.cache_dir / "llm")
    redactor = PiiRedactor()
    sanitizer = PdfSanitizer(max_size_mb=cfg.max_pdf_size_mb)

    effective_api_key = api_key or (
        cfg.gemini_api_key.get_secret_value() if cfg.gemini_api_key else None
    )
    if use_stub or cfg.use_stub_model or not effective_api_key:
        client = StubGeminiClient()
    else:
        client = GeminiClient(api_key=effective_api_key)

    gateway = ModelGateway(
        client=client,
        cost_tracker=cost_tracker,
        audit_logger=audit_logger,
        cache=cache,
        redactor=redactor,
        sanitizer=sanitizer,
    )
    return InsuranceMMRAGPipeline(gateway=gateway, settings=cfg)
