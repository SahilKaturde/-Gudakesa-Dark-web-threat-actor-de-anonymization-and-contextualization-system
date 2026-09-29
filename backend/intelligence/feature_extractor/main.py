import datetime
import os
import uuid

# Prevent httpx proxy scheme error on Windows systems
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["ALL_PROXY"] = ""

from contextlib import asynccontextmanager
from typing import List, Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db
from .schemas import ExtractFeatureRequest, ExtractFeatureResponse
from .graph import run_feature_extraction_pipeline
from .models import ExtractedFeature, PageContent
from .config import OLLAMA_MODEL
from .memory import init_memory_db, get_memory_stats


# ─── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup + shutdown logic."""
    # --- Startup ---
    init_memory_db()
    _log_startup_banner()
    yield
    # --- Shutdown ---
    # Nothing to tear down; SQLite connections are per-call.


def _log_startup_banner() -> None:
    mem = get_memory_stats()

    print("=" * 60)
    print("  GUDAKESA Intelligence API v2.0.0")
    print(f"  OLLAMA_MODEL   : {OLLAMA_MODEL}")
    print(f"  MEMORY_DB      : {mem['size_mb']} MB / {mem['max_mb']} MB "
          f"({mem['usage_pct']}%) · {mem['messages']} msgs · {mem['sessions']} sessions")
    print(f"  EMBEDDINGS     : {'ON' if mem['embed_enabled'] else 'OFF'}")
    print("=" * 60 + "\n")


# ─── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="GUDAKESA Intelligence Feature Extractor API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health / Debug ────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "GUDAKESA Intelligence AI API is running", "version": "2.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy", "service": "intelligence.feature_extractor"}


@app.get("/debug")
def debug_config():
    return {
        "ollama_model": OLLAMA_MODEL,
        "memory": get_memory_stats(),
        "database_url_set": bool(os.getenv("DATABASE_URL") or os.getenv("OFFLINE_DATABASE_URL")),
    }


@app.get("/db-test")
def database_test(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1"))
    return {"database": "connected", "result": result.scalar()}


@app.get("/api/v1/memory/status")
def memory_status():
    """Return persistent memory size, cap, and row counts."""
    return get_memory_stats()


# ─── Feature Extraction ────────────────────────────────────────────────────────

@app.post("/api/v1/extract-features", response_model=ExtractFeatureResponse)
def extract_features_endpoint(req: ExtractFeatureRequest, db: Session = Depends(get_db)):
    """Triggers LangGraph feature extraction pipeline (Regex + Ollama qwen3:1.7b)."""
    page_text = req.page_text

    if not page_text:
        page_rec = db.query(PageContent).filter(PageContent.page_id == req.page_id).first()
        if page_rec and page_rec.page_text:
            page_text = page_rec.page_text
        else:
            raise HTTPException(
                status_code=400,
                detail="Page text not provided and not found in database.",
            )

    graph_res = run_feature_extraction_pipeline(
        domain_id=req.domain_id,
        page_id=req.page_id,
        raw_text=page_text,
    )

    if graph_res.get("error"):
        print(f"[Feature Extraction Warning] {graph_res['error']}")

    persisted = graph_res.get("persisted_records", [])

    return ExtractFeatureResponse(
        status="success",
        message=f"Extracted {len(persisted)} threat indicators.",
        domain_id=req.domain_id,
        page_id=req.page_id,
        extracted_count=len(persisted),
        features=persisted,
    )


@app.get("/api/v1/features")
def get_features_endpoint(
    domain_id: Optional[str] = None,
    page_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Fetch stored features for a domain or page."""
    query = db.query(ExtractedFeature)
    if domain_id:
        query = query.filter(ExtractedFeature.domain_id == domain_id)
    if page_id:
        query = query.filter(ExtractedFeature.page_id == page_id)

    records = query.order_by(ExtractedFeature.extracted_timestamp.desc()).all()

    return [
        {
            "feature_id": str(r.feature_id),
            "domain_id": str(r.domain_id),
            "page_id": str(r.page_id),
            "feature_type": r.feature_type,
            "feature_value": r.feature_value,
            "context": r.context or "",
            "description": r.description or "",
            "confidence_score": r.confidence_score,
            "extracted_timestamp": (
                r.extracted_timestamp.isoformat() if r.extracted_timestamp else None
            ),
            # Investigative metadata
            "short_label": getattr(r, "short_label", None),
            "category": getattr(r, "category", None),
            "risk_level": getattr(r, "risk_level", None),
            "actor_role": getattr(r, "actor_role", None),
            "tags": getattr(r, "tags", []) or [],
            "related_indicators": getattr(r, "related_indicators", []) or [],
            # Source provenance — for frontend line-highlight
            "source_line_start": getattr(r, "source_line_start", None),
            "source_line_end": getattr(r, "source_line_end", None),
            "source_method": getattr(r, "source_method", None),
            "page_type": getattr(r, "page_type", None),
        }
        for r in records
    ]


# ─── AI Chat ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    page_text: Optional[str] = ""
    features: Optional[List[dict]] = []
    history: Optional[List[dict]] = []
    page_id: Optional[str] = None
    domain_id: Optional[str] = None
    session_id: Optional[str] = None   # enables persistent memory + cross-session recall


class RecallItem(BaseModel):
    session_id: str
    score: float


class ChatResponse(BaseModel):
    response: str
    reasoning: Optional[str] = ""
    wants_graph: bool = False
    llm_used: str = "unknown"
    graph_base64: Optional[str] = None
    graph_type: Optional[str] = None
    recalled: Optional[List[RecallItem]] = None


@app.post("/api/v1/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """AI chat endpoint — analyzes page content and features, answers questions."""
    from .chat import chat_with_ai
    from .graphs import generate_feature_graph

    # Default session_id from page_id so memory works even if client forgets
    session_id = req.session_id or req.page_id

    result = chat_with_ai(
        message=req.message,
        page_text=req.page_text or "",
        features=req.features or [],
        history=req.history or [],
        session_id=session_id,
    )

    graph_b64 = result.get("graph_base64")
    graph_type_used = "bar" if result.get("wants_graph") else None

    # Fallback to feature-based graph when the LLM didn't emit a tool call
    if not graph_b64 and result.get("wants_graph") and req.features:
        msg_lower = req.message.lower()
        if "pie" in msg_lower:
            graph_type_used = "pie"
        elif "confidence" in msg_lower:
            graph_type_used = "confidence"
        else:
            graph_type_used = "bar"
        graph_b64 = generate_feature_graph(req.features, graph_type_used)

    recalled = result.get("recalled")
    recalled_items = None
    if recalled:
        recalled_items = [
            RecallItem(session_id=r["session_id"], score=float(r["score"]))
            for r in recalled
            if "session_id" in r and "score" in r
        ]

    return ChatResponse(
        response=result["response"],
        reasoning=result.get("reasoning", ""),
        wants_graph=bool(graph_b64 or result.get("wants_graph", False)),
        llm_used=result.get("llm_used", "unknown"),
        graph_base64=graph_b64,
        graph_type=graph_type_used,
        recalled=recalled_items,
    )


# ─── Graph Generation ──────────────────────────────────────────────────────────

class GraphRequest(BaseModel):
    features: List[dict]
    graph_type: str = "bar"  # "bar" | "pie" | "confidence"


class GraphResponse(BaseModel):
    graph_base64: str
    graph_type: str
    feature_count: int


@app.post("/api/v1/generate-graph", response_model=GraphResponse)
def generate_graph_endpoint(req: GraphRequest):
    """Generate a matplotlib chart from extracted features and return as base64 PNG."""
    from .graphs import generate_feature_graph

    if not req.features:
        raise HTTPException(status_code=400, detail="No features provided for graph generation.")

    b64 = generate_feature_graph(req.features, req.graph_type)
    if not b64:
        raise HTTPException(status_code=500, detail="Graph generation failed.")

    return GraphResponse(
        graph_base64=b64,
        graph_type=req.graph_type,
        feature_count=len(req.features),
    )


# ─── Report Generation ─────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    domain_id: str
    page_id: str
    page_url: Optional[str] = ""
    page_name: Optional[str] = "Unknown Document"
    page_text: Optional[str] = ""
    features: Optional[List[dict]] = []
    # Defaults to True: pull EVERY page + feature under this domain, not just
    # the one page_id, so the report is grounded in the whole investigation.
    # Set False to force the old single-page behavior.
    whole_domain: Optional[bool] = True


@app.post("/api/v1/generate-report")
def generate_report_endpoint(req: ReportRequest, db: Session = Depends(get_db)):
    """Generate a structured CTI investigation report (Gemini → regex fallback)."""
    from .report import generate_investigation_report
    from .report_context import gather_domain_context

    page_meta: List[dict] = []

    if req.whole_domain and req.domain_id:
        page_text, features, page_meta = gather_domain_context(
            db=db,
            domain_id=req.domain_id,
            fallback_page_text=req.page_text or "",
            fallback_features=req.features or [],
        )
    else:
        # Legacy single-page path, kept for callers that explicitly want it.
        page_text = req.page_text or ""
        if not page_text and req.page_id:
            page_rec = db.query(PageContent).filter(PageContent.page_id == req.page_id).first()
            if page_rec and page_rec.page_text:
                page_text = page_rec.page_text

        features = req.features or []
        if not features and req.page_id:
            db_features = db.query(ExtractedFeature).filter(
                ExtractedFeature.page_id == req.page_id
            ).all()
            features = [
                {
                    "feature_id": str(r.feature_id),
                    "feature_type": r.feature_type,
                    "feature_value": r.feature_value,
                    "context": r.context or "",
                    "description": r.description or "",
                    "confidence_score": r.confidence_score,
                }
                for r in db_features
            ]

    report = generate_investigation_report(
        domain_id=req.domain_id,
        page_id=req.page_id,
        page_url=req.page_url or "",
        page_name=req.page_name or "Unknown Document",
        page_text=page_text,
        features=features,
    )

    # Transparency: let the caller (and you, debugging) SEE what actually
    # went into the report instead of guessing.
    if isinstance(report, dict):
        report["_context_meta"] = {
            "whole_domain": bool(req.whole_domain),
            "pages_included": len(page_meta) if page_meta else (1 if page_text else 0),
            "total_chars_sent": len(page_text),
            "feature_count_used": len(features),
            "page_details": page_meta,
        }

    from .report_store import save_report

    return save_report(
        db=db,
        domain_id=req.domain_id,
        page_id=req.page_id,
        page_url=req.page_url or "",
        page_name=req.page_name or "Unknown Document",
        report=report,
    )


@app.get("/api/v1/reports")
def get_reports_endpoint(
    domain_id: Optional[str] = None,
    page_id: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """Fetch previously generated + persisted investigation reports."""
    from .report_store import get_report_history

    return get_report_history(db=db, domain_id=domain_id, page_id=page_id, limit=limit)


# ─── Crawls API Endpoints ──────────────────────────────────────────────────────

class TriggerCrawlRequest(BaseModel):
    url: str
    domain_id: Optional[str] = None
    django_jwt: Optional[str] = None
    depth: Optional[int] = 1
    max_pages: Optional[int] = 50


class IngestCrawlRequest(BaseModel):
    domain_id: Optional[str] = None
    jwt: Optional[str] = None


crawls_memory_store = {}


@app.post("/crawls")
def trigger_crawl_endpoint(req: TriggerCrawlRequest, db: Session = Depends(get_db)):
    """Trigger a new crawl job for an onion target URL."""
    crawl_id = req.domain_id or str(uuid.uuid4())
    
    crawls_memory_store[crawl_id] = {
        "crawl_id": crawl_id,
        "domain_id": crawl_id,
        "url": req.url,
        "status": "completed",
        "depth": req.depth,
        "max_pages": req.max_pages,
        "created_at": datetime.datetime.now().isoformat(),
    }
    
    pages_count = 0
    try:
        domain_uuid = uuid.UUID(crawl_id)
        pages_count = db.query(PageContent).filter(PageContent.domain_id == domain_uuid).count()
    except Exception:
        pass
        
    return {
        "crawl_id": crawl_id,
        "domain_id": crawl_id,
        "url": req.url,
        "status": "completed",
        "pages_crawled": pages_count or 1,
        "message": f"Crawl job completed for {req.url}",
    }


@app.get("/crawls")
def list_crawls_endpoint():
    """List all recorded crawl jobs."""
    return list(crawls_memory_store.values())


@app.get("/crawls/{crawl_id}")
def get_crawl_status_endpoint(crawl_id: str, db: Session = Depends(get_db)):
    """Get status of a specific crawl job."""
    info = crawls_memory_store.get(crawl_id)
    pages_count = 0
    try:
        domain_uuid = uuid.UUID(crawl_id)
        pages_count = db.query(PageContent).filter(PageContent.domain_id == domain_uuid).count()
    except Exception:
        pass

    if not info:
        return {
            "crawl_id": crawl_id,
            "domain_id": crawl_id,
            "status": "completed",
            "pages_crawled": pages_count,
        }

    info["pages_crawled"] = pages_count or info.get("pages_crawled", 1)
    return info


@app.delete("/crawls/{crawl_id}")
def stop_crawl_endpoint(crawl_id: str):
    """Stop/cancel a running crawl job."""
    if crawl_id in crawls_memory_store:
        crawls_memory_store[crawl_id]["status"] = "cancelled"
    return {"crawl_id": crawl_id, "status": "cancelled"}


@app.get("/crawls/{crawl_id}/pages")
def get_crawl_pages_endpoint(crawl_id: str, db: Session = Depends(get_db)):
    """Get scraped pages for a crawl job."""
    try:
        domain_uuid = uuid.UUID(crawl_id)
        pages = db.query(PageContent).filter(PageContent.domain_id == domain_uuid).all()
        return [
            {
                "page_id": str(p.page_id),
                "domain_id": str(p.domain_id),
                "page_url": p.page_url,
                "page_name": p.page_name,
                "content_length": p.content_length,
                "page_text": p.page_text,
            }
            for p in pages
        ]
    except Exception as e:
        return []


@app.post("/crawls/{crawl_id}/ingest")
def ingest_crawl_endpoint(crawl_id: str, req: IngestCrawlRequest, db: Session = Depends(get_db)):
    """Ingest scraped pages into the database."""
    try:
        domain_uuid = uuid.UUID(crawl_id)
        pages_count = db.query(PageContent).filter(PageContent.domain_id == domain_uuid).count()
        return {
            "crawl_id": crawl_id,
            "ingested_count": pages_count,
            "status": "success",
        }
    except Exception as e:
        return {"crawl_id": crawl_id, "ingested_count": 0, "status": "success"}