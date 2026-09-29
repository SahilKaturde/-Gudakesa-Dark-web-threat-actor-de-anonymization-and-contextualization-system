"""
extractor/summarizer.py
Investigator-focused page summaries.
Uses qwen3:1.7b when Ollama is running, with rich templated fallback when offline.
"""
from typing import Any, Dict
from .llm.client import ask_qwen, is_ollama_available
from .llm.prompts import PAGE_SUMMARY, CHUNK_MERGE_SUMMARY
from .llm.fallback_extractor import chunk_text
from .loader import TextLoader


def summarize_page_llm(loader: TextLoader) -> str:
    """Generate high-density summary via qwen3:1.7b."""
    core = loader.get_core_text()
    if not core.strip():
        return "Empty page."

    chunks = chunk_text(core)
    if len(chunks) == 1:
        prompt = PAGE_SUMMARY.format(chunk=chunks[0]["text"])
        return ask_qwen(prompt, max_tokens=150) or ""

    chunk_summaries = []
    for c in chunks[:4]:
        prompt = PAGE_SUMMARY.format(chunk=c["text"])
        s = ask_qwen(prompt, max_tokens=100)
        if s:
            chunk_summaries.append(s)

    if not chunk_summaries:
        return ""

    if len(chunk_summaries) == 1:
        return chunk_summaries[0]

    merged_prompt = CHUNK_MERGE_SUMMARY.format(
        summaries="\n".join(f"- {s}" for s in chunk_summaries)
    )
    return ask_qwen(merged_prompt, max_tokens=150) or chunk_summaries[0]


def summarize_page_template(loader: TextLoader, features: Dict[str, Any]) -> str:
    """Structured intelligence summary crafted without LLM."""
    ptype = features.get("page_type", "GENERAL")
    product = features.get("product")
    vendor = features.get("vendor")
    reviews = features.get("reviews") or []
    catalog = features.get("catalog_products") or []

    parts = []

    if ptype == "PRODUCT_DETAIL" and product and product.get("title"):
        p_str = ""
        prices = product.get("prices") or {}
        if prices.get("current"):
            p_str = f" priced at ${prices['current']}"
        elif prices.get("listed"):
            p_str = f" priced at ${prices['listed']}"
        elif prices.get("range_low"):
            p_str = f" priced ${prices['range_low']}-${prices['range_high']}"

        cat = product.get("category") or product.get("category_path") or "unspecified category"
        parts.append(f"Product listing for '{product['title']}'{p_str} in category '{cat}'.")

        if vendor and vendor.get("name"):
            v_rating = f" (rated {vendor['rating']}/5)" if vendor.get("rating") else ""
            parts.append(f"Offered by {vendor.get('type', 'vendor').replace('_', ' ')} '{vendor['name']}'{v_rating}.")

        if reviews:
            parts.append(f"Contains {len(reviews)} customer feedback review(s).")
        elif product.get("overall_rating"):
            parts.append(f"Overall rating: {product['overall_rating']}/5 ({product.get('review_count', 0)} ratings).")

    elif ptype == "CATALOG_LISTING":
        first_line = loader.lines[0] if loader.lines else ""
        cat_name = "Marketplace Catalog"
        if "archives -" in first_line.lower():
            cat_name = first_line.split("Archives -")[0].strip()
        parts.append(f"Catalog listing / category archive for '{cat_name}' listing {len(catalog)} item(s).")
        if vendor and vendor.get("name"):
            parts.append(f"Hosted on '{vendor['name']}'.")

    else:
        first_line = loader.lines[0] if loader.lines else "General Info"
        first_clean = first_line.split("Skip to")[0].strip()
        parts.append(f"Informational / navigation page ({first_clean}).")
        if "frequently asked" in loader.raw_text.lower():
            parts.append("Outlines marketplace policies, cryptocurrency payments, shipping, and security FAQ.")
        elif "contact" in loader.raw_text.lower():
            parts.append("Provides contact channels and customer support routing.")
        elif "onion index" in loader.raw_text.lower():
            parts.append("Dark web index / search engine directory page.")

    return " ".join(parts) if parts else "Marketplace intelligence page."


def summarize_page(loader: TextLoader, features: Dict[str, Any]) -> str:
    """Produce investigator summary (LLM if available, template otherwise)."""
    if is_ollama_available():
        llm_sum = summarize_page_llm(loader)
        if llm_sum:
            return llm_sum

    return summarize_page_template(loader, features)
