import uuid
import datetime
from typing import List, Dict, Any, Optional, TypedDict
from langgraph.graph import StateGraph, END

from .schemas import ExtractedEntityItem
from .extractor import extract_features_with_llm
from .database import SessionLocal
from .models import ExtractedFeature, PageContent, CrawledDomain


class ExtractionGraphState(TypedDict):
    domain_id: str
    page_id: str
    raw_text: str
    cleaned_text: str
    extracted_items: List[ExtractedEntityItem]
    validated_items: List[ExtractedEntityItem]
    persisted_records: List[Dict[str, Any]]
    error: Optional[str]


def node_sanitize_text(state: ExtractionGraphState) -> ExtractionGraphState:
    """Node 1: Clean raw scraped text."""
    raw = state.get("raw_text", "")
    if not raw and state.get("page_id"):
        db = SessionLocal()
        try:
            p = db.query(PageContent).filter(PageContent.page_id == state["page_id"]).first()
            if p and p.page_text:
                raw = p.page_text
        finally:
            db.close()

    cleaned = raw.replace("\r", " ").strip()
    return {
        **state,
        "raw_text": raw,
        "cleaned_text": cleaned
    }


def node_extract(state: ExtractionGraphState) -> ExtractionGraphState:
    """Node 2: Call OpenRouter LangChain Gemini Flash extractor."""
    text = state.get("cleaned_text", "")
    if not text:
        return {**state, "extracted_items": [], "error": "No page text available for extraction."}

    items = extract_features_with_llm(text)
    return {
        **state,
        "extracted_items": items
    }


def node_validate_and_score(state: ExtractionGraphState) -> ExtractionGraphState:
    """Node 3: Filter duplicates and calibrate confidence scores."""
    raw_items = state.get("extracted_items", [])
    validated = []
    seen = set()

    for item in raw_items:
        key = (item.feature_type.lower(), item.feature_value.strip().lower())
        if key in seen:
            continue
        seen.add(key)

        score = item.confidence_score
        if score is None or score <= 0:
            score = 0.7
        score = min(1.0, max(0.1, round(float(score), 2)))

        item.confidence_score = score
        item.feature_value = item.feature_value.strip()
        item.context = item.context[:250].strip() if item.context else ""
        item.description = item.description[:250].strip() if item.description else ""

        validated.append(item)

    return {
        **state,
        "validated_items": validated
    }


def node_persist(state: ExtractionGraphState) -> ExtractionGraphState:
    """Node 4: Write features to Supabase PostgreSQL feature_extractedfeature table."""
    domain_id = state.get("domain_id")
    page_id = state.get("page_id")
    items = state.get("validated_items", [])

    if not items or not domain_id or not page_id:
        return {**state, "persisted_records": []}

    db = SessionLocal()
    persisted = []
    now = datetime.datetime.now(datetime.timezone.utc)

    try:
        existing = db.query(ExtractedFeature).filter(
            ExtractedFeature.domain_id == domain_id,
            ExtractedFeature.page_id == page_id
        ).all()

        existing_keys = {(e.feature_type.lower(), e.feature_value.strip().lower()) for e in existing}

        for item in items:
            key = (item.feature_type.lower(), item.feature_value.strip().lower())
            if key in existing_keys:
                continue

            f_id = uuid.uuid4()
            record = ExtractedFeature(
                feature_id=f_id,
                domain_id=domain_id,
                page_id=page_id,
                feature_type=item.feature_type,
                feature_value=item.feature_value,
                context=item.context,
                description=item.description,
                confidence_score=item.confidence_score,
                extracted_timestamp=now
            )
            db.add(record)
            existing_keys.add(key)

            persisted.append({
                "feature_id": str(f_id),
                "domain_id": str(domain_id),
                "page_id": str(page_id),
                "feature_type": item.feature_type,
                "feature_value": item.feature_value,
                "context": item.context,
                "description": item.description,
                "confidence_score": item.confidence_score,
                "extracted_timestamp": now.isoformat()
            })

        db.commit()

        if not persisted:
            for item in items:
                persisted.append({
                    "feature_id": str(uuid.uuid4()),
                    "domain_id": str(domain_id),
                    "page_id": str(page_id),
                    "feature_type": item.feature_type,
                    "feature_value": item.feature_value,
                    "context": item.context or "",
                    "description": item.description or "",
                    "confidence_score": item.confidence_score,
                    "extracted_timestamp": now.isoformat()
                })

    except Exception as e:
        db.rollback()
        print(f"[LangGraph Persist Warning] {e}. Returning extracted items in-memory.")
        persisted = [
            {
                "feature_id": str(uuid.uuid4()),
                "domain_id": str(domain_id),
                "page_id": str(page_id),
                "feature_type": item.feature_type,
                "feature_value": item.feature_value,
                "context": item.context or "",
                "description": item.description or "",
                "confidence_score": item.confidence_score,
                "extracted_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
            for item in items
        ]
        return {**state, "error": str(e), "persisted_records": persisted}
    finally:
        db.close()

    return {
        **state,
        "persisted_records": persisted
    }


# Build LangGraph Workflow
builder = StateGraph(ExtractionGraphState)

builder.add_node("sanitize_text", node_sanitize_text)
builder.add_node("extract", node_extract)
builder.add_node("validate_and_score", node_validate_and_score)
builder.add_node("persist", node_persist)

builder.set_entry_point("sanitize_text")
builder.add_edge("sanitize_text", "extract")
builder.add_edge("extract", "validate_and_score")
builder.add_edge("validate_and_score", "persist")
builder.add_edge("persist", END)

extraction_graph = builder.compile()


def run_feature_extraction_pipeline(domain_id: str, page_id: str, raw_text: Optional[str] = None) -> Dict[str, Any]:
    """Runner function for the LangGraph feature extraction graph."""
    initial_state: ExtractionGraphState = {
        "domain_id": domain_id,
        "page_id": page_id,
        "raw_text": raw_text or "",
        "cleaned_text": "",
        "extracted_items": [],
        "validated_items": [],
        "persisted_records": [],
        "error": None
    }

    final_state = extraction_graph.invoke(initial_state)
    return final_state
