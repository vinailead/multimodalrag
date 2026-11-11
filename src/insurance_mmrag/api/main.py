"""FastAPI backend exposing REST endpoints, health, telemetry, audit logs, and MCP tools."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from insurance_mmrag.config import get_settings
from insurance_mmrag.evals.benchmark_runner import BenchmarkRunner
from insurance_mmrag.ingestion.sample_policy_factory import (
    create_arogya_sanjeevani_pdf,
    create_saral_suraksha_bima_pdf,
)
from insurance_mmrag.mcp_tools import MCPToolServer
from insurance_mmrag.pipeline import InsuranceMMRAGPipeline, create_default_pipeline
from insurance_mmrag.schemas import (
    AdvisorRecommendationResponse,
    ApplicantProfile,
    AuditLogEntry,
    ClaimSimulationResponse,
    FinOpsSummary,
    GroundedQueryResponse,
    PolicyComparisonResponse,
    RAGTriadScorecard,
)

# Global pipeline instance
logger = logging.getLogger(__name__)
_pipeline: InsuranceMMRAGPipeline | None = None
_mcp_server: MCPToolServer | None = None


def get_pipeline() -> InsuranceMMRAGPipeline:
    global _pipeline, _mcp_server
    if _pipeline is None:
        _pipeline = create_default_pipeline()
        # Seed with Arogya Sanjeevani sample if empty
        settings = get_settings()
        sample_path = settings.raw_policies_dir / "arogya_sanjeevani_policy_wordings.pdf"
        if not sample_path.exists():
            create_arogya_sanjeevani_pdf(sample_path)
        _pipeline.ingest_pdf(sample_path, doc_id="arogya_sanjeevani_national")

        sample_path_saral = settings.raw_policies_dir / "saral_suraksha_bima.pdf"
        if not sample_path_saral.exists():
            create_saral_suraksha_bima_pdf(sample_path_saral)
        _pipeline.ingest_pdf(sample_path_saral, doc_id="saral_suraksha_bima_hdfc")

        _mcp_server = MCPToolServer(_pipeline)
    return _pipeline


def get_mcp_server() -> MCPToolServer:
    global _mcp_server
    if _mcp_server is None:
        get_pipeline()
    return _mcp_server or MCPToolServer(get_pipeline())


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup: ensure pipeline is initialized
    get_pipeline()
    yield


app = FastAPI(
    title="Indian Insurance Multimodal RAG API",
    version="1.0.0",
    description="Enterprise Structure-Aware Multimodal RAG for IRDAI Policies",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- Models
class HealthResponse(BaseModel):
    status: str
    version: str
    vector_store: str
    indexed_policies_count: int
    total_chunks_count: int


class PolicySummaryItem(BaseModel):
    doc_id: str
    policy_name: str
    insurer_name: str
    uin: str
    page_count: int
    parents_count: int
    children_count: int
    tables_count: int


class QueryRequest(BaseModel):
    query: str = Field(min_length=2, description="The insurance question to query.")
    doc_id: str | None = Field(default=None, description="Optional doc_id to scope retrieval.")
    top_k: int = Field(default=6, ge=1, le=20)


class IngestPathRequest(BaseModel):
    pdf_path: str
    doc_id: str | None = None


class IngestResponse(BaseModel):
    doc_id: str
    policy_name: str
    uin: str
    pages: int
    parents_created: int
    children_created: int
    tables_extracted: int


class McpExecuteRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class AdvisorRecommendRequest(BaseModel):
    query: str = Field(
        default="I am individual with age 26, non smoker and non drinker with family of 5 what is the best policy for me",
        min_length=2,
        description="Natural language advisory query or family description.",
    )
    profile: ApplicantProfile | None = Field(
        default=None,
        description="Optional structured ApplicantProfile overrides from interactive probing answers.",
    )


class PolicyCompareRequest(BaseModel):
    doc_ids: list[str] | None = Field(
        default=None,
        description="List of policy doc_ids to compare side-by-side.",
    )
    profile: ApplicantProfile | None = Field(
        default=None,
        description="Optional ApplicantProfile for personalized premium calculation.",
    )


class ClaimSimulateRequest(BaseModel):
    claimed_bill_inr: int = Field(default=150_000, ge=1_000)
    hospital_room_rent_per_day_inr: int = Field(default=8_000, ge=500)
    days_hospitalized: int = Field(default=3, ge=1)
    procedure_type: str = Field(default="general_hospitalization")
    sum_insured_inr: int = Field(default=1_000_000, ge=100_000)
    doc_ids: list[str] | None = None


# --------------------------------------------------------------------------- Endpoints
@app.get("/api/v1/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    pipe = get_pipeline()
    docs = pipe.get_indexed_documents()
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        vector_store="ready",
        indexed_policies_count=len(docs),
        total_chunks_count=pipe.vector_store.count(),
    )


@app.get("/api/v1/policies", response_model=list[PolicySummaryItem])
def list_policies() -> list[PolicySummaryItem]:
    pipe = get_pipeline()
    docs = pipe.get_indexed_documents()
    items: list[PolicySummaryItem] = []
    seen_ids: set[str] = set()

    for doc in docs.values():
        seen_ids.add(doc.structure.doc_id)
        items.append(
            PolicySummaryItem(
                doc_id=doc.structure.doc_id,
                policy_name=doc.structure.policy_name,
                insurer_name=doc.structure.insurer_name,
                uin=doc.structure.uin,
                page_count=doc.structure.page_count,
                parents_count=len(doc.parents),
                children_count=len(doc.children),
                tables_count=len(doc.tables),
            )
        )

    # Include available provider policies from manifest.json
    settings = get_settings()
    manifest_file = settings.raw_policies_dir / "manifest.json"
    if manifest_file.exists():
        try:
            import json

            entries = json.loads(manifest_file.read_text(encoding="utf-8"))
            for entry in entries:
                doc_id = entry.get("doc_id", "")
                if doc_id and doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    items.append(
                        PolicySummaryItem(
                            doc_id=doc_id,
                            policy_name=entry.get("policy_name", doc_id),
                            insurer_name=entry.get("insurer_name", "Unknown Insurer"),
                            uin=entry.get("uin", "UNKNOWN_UIN"),
                            page_count=int(entry.get("pages", 1)),
                            parents_count=0,
                            children_count=0,
                            tables_count=0,
                        )
                    )
        except Exception as exc:
            logger.debug("Failed reading manifest for policy list: %s", exc)

    return items


@app.post("/api/v1/ingest", response_model=IngestResponse)
async def ingest_policy(
    file: UploadFile | None = None,
    path_req: IngestPathRequest | None = None,
) -> IngestResponse:
    pipe = get_pipeline()
    settings = get_settings()

    if file is not None:
        target_path = settings.raw_policies_dir / (file.filename or "uploaded_policy.pdf")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        content = await file.read()
        target_path.write_bytes(content)
        doc_id = Path(file.filename or "uploaded").stem
        ingested = pipe.ingest_pdf(target_path, doc_id=doc_id)
    elif path_req is not None:
        target_path = Path(path_req.pdf_path)
        if not target_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path_req.pdf_path}")
        ingested = pipe.ingest_pdf(target_path, doc_id=path_req.doc_id)
    else:
        raise HTTPException(
            status_code=400, detail="Must provide either a file upload or pdf_path."
        )

    return IngestResponse(
        doc_id=ingested.structure.doc_id,
        policy_name=ingested.structure.policy_name,
        uin=ingested.structure.uin,
        pages=ingested.structure.page_count,
        parents_created=len(ingested.parents),
        children_created=len(ingested.children),
        tables_extracted=len(ingested.tables),
    )


@app.post("/api/v1/query", response_model=GroundedQueryResponse)
def query_policy(req: QueryRequest) -> GroundedQueryResponse:
    pipe = get_pipeline()
    if req.doc_id and req.doc_id not in pipe.get_indexed_documents():
        settings = get_settings()
        manifest_file = settings.raw_policies_dir / "manifest.json"
        if manifest_file.exists():
            try:
                import json

                entries = json.loads(manifest_file.read_text(encoding="utf-8"))
                for entry in entries:
                    if entry.get("doc_id") == req.doc_id:
                        file_path = Path(entry.get("file_path", ""))
                        if not file_path.is_absolute():
                            file_path = Path.cwd() / file_path
                        if file_path.exists():
                            pipe.ingest_pdf(file_path, doc_id=req.doc_id)
                        break
            except Exception as exc:
                logger.debug("Failed on-demand ingestion for %s: %s", req.doc_id, exc)
    return pipe.query(user_query=req.query, doc_id=req.doc_id, top_k=req.top_k)


@app.post("/api/v1/advisor/recommend", response_model=AdvisorRecommendationResponse)
def recommend_policies_endpoint(req: AdvisorRecommendRequest) -> AdvisorRecommendationResponse:
    pipe = get_pipeline()
    return pipe.recommend_policies(user_query=req.query, profile=req.profile)


@app.post("/api/v1/policies/compare", response_model=PolicyComparisonResponse)
def compare_policies_endpoint(req: PolicyCompareRequest) -> PolicyComparisonResponse:
    pipe = get_pipeline()
    try:
        return pipe.compare_policies(doc_ids=req.doc_ids, profile=req.profile)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/policies/simulate-claim", response_model=ClaimSimulationResponse)
def simulate_claim_endpoint(req: ClaimSimulateRequest) -> ClaimSimulationResponse:
    pipe = get_pipeline()
    try:
        return pipe.simulate_claim(
            claimed_bill_inr=req.claimed_bill_inr,
            hospital_room_rent_per_day_inr=req.hospital_room_rent_per_day_inr,
            days_hospitalized=req.days_hospitalized,
            procedure_type=req.procedure_type,
            sum_insured_inr=req.sum_insured_inr,
            doc_ids=req.doc_ids,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/crops/{crop_filename}")
def serve_crop(crop_filename: str) -> FileResponse:
    settings = get_settings()
    crop_path = settings.crops_dir / crop_filename
    if not crop_path.exists():
        raise HTTPException(status_code=404, detail="Crop image not found")
    return FileResponse(str(crop_path), media_type="image/png")


@app.get("/api/v1/telemetry/cost", response_model=FinOpsSummary)
def get_cost_telemetry() -> FinOpsSummary:
    pipe = get_pipeline()
    return pipe.get_finops_summary()


@app.get("/api/v1/governance/audit", response_model=list[AuditLogEntry])
def get_audit_trail(limit: int = Query(default=50, ge=1, le=500)) -> list[AuditLogEntry]:
    pipe = get_pipeline()
    return pipe.gateway.audit.read(limit=limit)


@app.get("/api/v1/benchmark/scorecard", response_model=RAGTriadScorecard)
def get_benchmark_scorecard() -> RAGTriadScorecard:
    pipe = get_pipeline()
    runner = BenchmarkRunner(pipe)
    return runner.run_benchmark()


@app.get("/api/v1/mcp/tools")
def get_mcp_tools() -> list[dict[str, Any]]:
    return get_mcp_server().list_tools()


@app.post("/api/v1/mcp/execute")
def execute_mcp_tool(req: McpExecuteRequest) -> dict[str, Any]:
    return get_mcp_server().execute_tool(req.tool_name, req.arguments)


# Mount static web UI if built
dist_dir = Path("dist")
if dist_dir.exists():
    app.mount("/", StaticFiles(directory="dist", html=True), name="static")
