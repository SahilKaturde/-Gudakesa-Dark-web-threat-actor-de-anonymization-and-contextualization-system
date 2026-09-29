"""
extractor/llm/fallback_extractor.py
LLM fallback extraction for unfamiliar / non-standard .onion page structures.
"""
import logging
from typing import Any, Dict, List
from ..config import CHUNK_SIZE, CHUNK_OVERLAP
from .client import ask_qwen, is_ollama_available
from .prompts import PRODUCT_EXTRACTION, REVIEW_EXTRACTION, VENDOR_EXTRACTION
from .parser import parse_llm_json
from ..extractors.base import make_provenance
from ..loader import TextLoader

log = logging.getLogger(__name__)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[Dict[str, Any]]:
    """Chunk text with overlap to fit small context windows."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append({
            "text": text[start:end],
            "char_start": start,
            "char_end": end,
        })
        if end >= len(text):
            break
        start += chunk_size - overlap
    return chunks


def llm_fallback_extract(loader: TextLoader) -> Dict[str, Any]:
    """Execute LLM extraction when regex yields low confidence."""
    if not is_ollama_available():
        return {"product": {}, "reviews": [], "vendor": {}}

    core = loader.get_core_text()
    chunks = chunk_text(core)
    if not chunks:
        return {"product": {}, "reviews": [], "vendor": {}}

    prod_res = {}
    for c in chunks[:3]:
        raw = ask_qwen(PRODUCT_EXTRACTION.format(chunk=c["text"]))
        p = parse_llm_json(raw)
        if isinstance(p, dict) and p.get("product_name"):
            prod_res = p
            prod_res["provenance"] = make_provenance(loader.filename, method="llm", confidence=0.7)
            break

    reviews_res = []
    for c in chunks:
        raw = ask_qwen(REVIEW_EXTRACTION.format(chunk=c["text"]))
        r = parse_llm_json(raw)
        if isinstance(r, list):
            for item in r:
                if isinstance(item, dict) and (item.get("username") or item.get("comment")):
                    item["provenance"] = make_provenance(loader.filename, method="llm", confidence=0.65)
                    reviews_res.append(item)

    vendor_res = {}
    raw_v = ask_qwen(VENDOR_EXTRACTION.format(chunk=chunks[0]["text"]))
    v = parse_llm_json(raw_v)
    if isinstance(v, dict) and v.get("vendor_name"):
        vendor_res = v
        vendor_res["provenance"] = make_provenance(loader.filename, method="llm", confidence=0.7)

    return {
        "product": prod_res,
        "reviews": reviews_res,
        "vendor": vendor_res,
    }
