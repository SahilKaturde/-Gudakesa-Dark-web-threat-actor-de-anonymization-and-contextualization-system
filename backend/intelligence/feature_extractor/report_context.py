"""
Report context gathering.

This is the fix for reports being generated from a single page instead of
the whole crawled domain: the old /api/v1/generate-report handler filtered
PageContent and ExtractedFeature by page_id ONLY, so generate_investigation_report()
never saw anything else the crawler pulled in for that domain — no matter how
many other pages, vendors, or listings existed. That's the leading cause of
reports feeling incomplete or "off": the model was answering with a fraction
of the available evidence.
"""
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from .models import ExtractedFeature, PageContent

# Gemini 2.5 Flash comfortably takes ~1M input tokens (~4M chars). We cap well
# below that for cost/latency, but this is many times bigger than the old
# single-page 40k/24k character ceilings — enough for a full domain crawl of
# typical dark-web forum/market pages.
MAX_DOMAIN_CONTEXT_CHARS = 350_000


def gather_domain_context(
    db: Session,
    domain_id: str,
    fallback_page_text: str = "",
    fallback_features: Optional[List[Dict]] = None,
    max_chars: int = MAX_DOMAIN_CONTEXT_CHARS,
) -> Tuple[str, List[Dict], List[Dict]]:
    """
    Pull every page and every extracted feature belonging to `domain_id`,
    concatenated into one block with clear per-page headers so the model can
    still attribute claims to the right source page.

    Returns (combined_text, features, page_meta) where page_meta lists which
    pages actually made it into context (for transparency / debugging "did it
    really read everything").
    """
    pages = (
        db.query(PageContent)
        .filter(PageContent.domain_id == domain_id)
        .order_by(PageContent.crawl_timestamp.asc())
        .all()
    )

    combined_parts: List[str] = []
    page_meta: List[Dict] = []
    total_len = 0

    for p in pages:
        text = (p.page_text or "").strip()
        if not text:
            continue

        header = (
            f"\n\n===== PAGE: {p.page_name or '(untitled)'} "
            f"| URL: {p.page_url or '(no url)'} "
            f"| page_id: {p.page_id} =====\n"
        )
        chunk = header + text
        included_chars = len(chunk)

        if total_len + included_chars > max_chars:
            remaining = max_chars - total_len
            if remaining > 500:  # only bother with a partial page if it's worth it
                combined_parts.append(chunk[:remaining])
                page_meta.append({
                    "page_id": str(p.page_id),
                    "page_name": p.page_name,
                    "page_url": p.page_url,
                    "chars_included": remaining,
                    "truncated": True,
                })
            break

        combined_parts.append(chunk)
        total_len += included_chars
        page_meta.append({
            "page_id": str(p.page_id),
            "page_name": p.page_name,
            "page_url": p.page_url,
            "chars_included": len(text),
            "truncated": False,
        })

    combined_text = "".join(combined_parts).strip()

    # No pages found in the DB for this domain (e.g. an ad-hoc single-page
    # submission that was never crawled/stored) — fall back to whatever the
    # caller already had rather than returning an empty report.
    if not combined_text:
        combined_text = fallback_page_text or ""

    # Features across the WHOLE domain, not just one page.
    feature_rows = (
        db.query(ExtractedFeature)
        .filter(ExtractedFeature.domain_id == domain_id)
        .all()
    )
    features = [
        {
            "feature_id": str(r.feature_id),
            "page_id": str(r.page_id) if r.page_id else None,
            "feature_type": r.feature_type,
            "feature_value": r.feature_value,
            "context": r.context or "",
            "description": r.description or "",
            "confidence_score": r.confidence_score,
        }
        for r in feature_rows
    ]
    if not features:
        features = fallback_features or []

    return combined_text, features, page_meta
