import os
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


app = FastAPI(
    title="GUDAKESA Intelligence Feature Extractor API",
    version="2.0.0",
)


@app.on_event("startup")
async def startup_log():
    key = os.getenv("OPENROUTER_API_KEY", "")
    model = os.getenv("OPENROUTER_MODEL", "google/gemini-3.6-flash")
    key_status = f"SET ({key[:12]}...)" if key and not key.startswith("your_") else "NOT SET / INVALID"
    print(f"\n{'='*55}")
    print(f"  GUDAKESA Intelligence API v2.0.0")
    print(f"  OPENROUTER_API_KEY : {key_status}")
    print(f"  OPENROUTER_MODEL   : {model}")
    print(f"  OLLAMA_MODEL       : {os.getenv('OLLAMA_MODEL', 'qwen3:1.7b')}")
    print(f"{'='*55}\n")


# Enable CORS for React frontend
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
    key = os.getenv("OPENROUTER_API_KEY", "")
    key_status = f"SET ({key[:12]}...)" if key and not key.startswith("your_") else "NOT SET or INVALID"
    return {
        "openrouter_api_key_status": key_status,
        "openrouter_model": os.getenv("OPENROUTER_MODEL", "google/gemini-3.6-flash (default)"),
        "ollama_model": os.getenv("OLLAMA_MODEL", "qwen3:1.7b (default)"),
        "ollama_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434 (default)"),
        "database_url_set": bool(os.getenv("DATABASE_URL")),
    }


@app.get("/db-test")
def database_test(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1"))
    return {"database": "connected", "result": result.scalar()}


# ─── Feature Extraction ────────────────────────────────────────────────────────

@app.post("/api/v1/extract-features", response_model=ExtractFeatureResponse)
def extract_features_endpoint(req: ExtractFeatureRequest, db: Session = Depends(get_db)):
    """Triggers LangGraph feature extraction pipeline (OpenRouter → Ollama → Regex)."""
    page_text = req.page_text

    if not page_text:
        page_rec = db.query(PageContent).filter(PageContent.page_id == req.page_id).first()
        if page_rec and page_rec.page_text:
            page_text = page_rec.page_text
        else:
            raise HTTPException(status_code=400, detail="Page text not provided and not found in database.")

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
            "extracted_timestamp": r.extracted_timestamp.isoformat() if r.extracted_timestamp else None,
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


class ChatResponse(BaseModel):
    response: str
    wants_graph: bool = False
    llm_used: str = "unknown"
    graph_base64: Optional[str] = None
    graph_type: Optional[str] = None


@app.post("/api/v1/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """AI chat endpoint — analyzes page content and features, answers questions."""
    from .chat import chat_with_ai, GRAPH_KEYWORDS
    from .graphs import generate_feature_graph

    result = chat_with_ai(
        message=req.message,
        page_text=req.page_text or "",
        features=req.features or [],
        history=req.history or [],
    )

    graph_b64 = None
    graph_type_used = None

    # Auto-generate graph if user asked for one
    if result.get("wants_graph") and req.features:
        msg_lower = req.message.lower()
        if "pie" in msg_lower:
            graph_type_used = "pie"
        elif "confidence" in msg_lower:
            graph_type_used = "confidence"
        else:
            graph_type_used = "bar"
        graph_b64 = generate_feature_graph(req.features, graph_type_used)

    return ChatResponse(
        response=result["response"],
        wants_graph=result.get("wants_graph", False),
        llm_used=result.get("llm_used", "unknown"),
        graph_base64=graph_b64,
        graph_type=graph_type_used,
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


@app.post("/api/v1/generate-report")
def generate_report_endpoint(req: ReportRequest, db: Session = Depends(get_db)):
    """Generate a structured CTI investigation report (OpenRouter → Ollama → fallback)."""
    from .report import generate_investigation_report

    page_text = req.page_text or ""

    # Load page text from DB if not provided
    if not page_text and req.page_id:
        page_rec = db.query(PageContent).filter(PageContent.page_id == req.page_id).first()
        if page_rec and page_rec.page_text:
            page_text = page_rec.page_text

    # Load features from DB if not provided
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

    return report
