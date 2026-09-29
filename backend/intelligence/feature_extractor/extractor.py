"""
intelligence/feature_extractor/extractor.py

Hybrid Regex + Ollama (qwen3:1.7b) intelligence extraction pipeline
for law enforcement and investigative profiling of dark web (.onion) markets.

Architecture:
  1. TextLoader  — line-indexed access, boilerplate detection
  2. Classifier  — PRODUCT_DETAIL | CATALOG_LISTING | GENERAL
  3. Structured extractors:
       - product   → title, prices, specs, tags, sku, availability
       - vendor    → name, rating, contacts, crypto accepted
       - reviews   → author, rating, date, comment
       - catalog   → product cards from listing pages
       - sidebar   → categories, recent comments, top vendors
  4. Regex-pattern extraction — onion URLs, BTC/XMR wallets, emails,
       PGP keys, Telegram handles, XMPP addresses (applied across all pages)
  5. Ollama fallback (qwen3:1.7b) — only when regex yields < MIN_FEATURES_REGEX
  6. Summarizer — 2-sentence LLM or rich template summary

Every extracted item carries:
  source_line_start / source_line_end — 1-based line numbers into the raw page
  source_method                        — "regex", "regex_review", "regex_vendor",
                                         "regex_archive", "regex_card", "llm"
  confidence_score
  feature_type / feature_value / context / description
"""
import re
import io
from typing import Any, Dict, List, Optional, Tuple

from .loader import TextLoader
from .classifier import classify_page, PageType
from .extractors.product import extract_product
from .extractors.review import extract_reviews
from .extractors.vendor import extract_vendor, extract_top_vendors_sidebar
from .extractors.catalog import extract_catalog
from .extractors.sidebar import extract_sidebar
from . import patterns as pat
from .config import MIN_FEATURES_REGEX
from .llm.client import is_ollama_available
from .llm.fallback_extractor import llm_fallback_extract
from .summarizer import summarize_page
from .schemas import ExtractedEntityItem

# ---------------------------------------------------------------------------
# Investigative metadata lookups
# ---------------------------------------------------------------------------
CATEGORY_BY_TYPE: Dict[str, str] = {
    "email": "communication",
    "xmpp": "communication",
    "phone": "communication",
    "username": "identity",
    "pgp_key": "identity",
    "ip": "infrastructure",
    "onion_url": "infrastructure",
    "crypto_wallet": "financial",
    "financial_account": "financial",
    "product": "activity",
    "post": "activity",
    "review": "activity",
    "other": "other",
}

RISK_BY_TYPE: Dict[str, str] = {
    "crypto_wallet": "high",
    "financial_account": "high",
    "pgp_key": "medium",
    "email": "medium",
    "phone": "medium",
    "onion_url": "medium",
    "ip": "medium",
    "username": "low",
    "xmpp": "low",
    "product": "low",
    "post": "low",
    "review": "low",
    "other": "low",
}

# Short descriptions used for the description field on regex-only hits
_TYPE_LABEL: Dict[str, str] = {
    "email": "an email address",
    "username": "a handle, alias, or account identifier",
    "ip": "an IPv4 address",
    "crypto_wallet": "a cryptocurrency wallet address",
    "financial_account": "a bank account number (IBAN format, checksum-verified)",
    "pgp_key": "a PGP public key or fingerprint",
    "onion_url": "a Tor (.onion) hidden-service address",
    "xmpp": "an XMPP/Jabber address",
    "phone": "a phone number or phone-linked messaging contact",
}


# ---------------------------------------------------------------------------
# In-memory TextLoader (no file required — works from DB page_text)
# ---------------------------------------------------------------------------

class InMemoryTextLoader(TextLoader):
    """TextLoader subclass that accepts a raw string instead of a file path."""

    def __init__(self, text: str, filename: str = "page.txt"):
        # Bypass file reading — inject text directly
        import pathlib
        self.file_path = pathlib.Path(filename)
        self.filename = filename
        self._raw_text = text
        self._lines: List[str] = text.splitlines()
        self._core_start: int = 0
        self._core_end: int = len(self._lines)
        self._detect_boilerplate()


# ---------------------------------------------------------------------------
# Feature count helper
# ---------------------------------------------------------------------------

def count_features(features: Dict[str, Any]) -> int:
    """Count extracted features to assess confidence."""
    count = 0
    product = features.get("product")
    if product and isinstance(product, dict):
        if product.get("title"):
            count += 1
        if product.get("prices"):
            count += 1
        if product.get("category") or product.get("category_path"):
            count += 1
        if product.get("specs"):
            count += 1
        if product.get("tags"):
            count += 1

    vendor = features.get("vendor")
    if vendor and isinstance(vendor, dict) and vendor.get("name"):
        count += 1

    count += len(features.get("reviews") or [])
    count += len(features.get("catalog_products") or [])
    return count


# ---------------------------------------------------------------------------
# Description builder (no LLM call — deterministic analytical write-up)
# ---------------------------------------------------------------------------

def _make_description(f_type: str, value: str, snippet: str, method: str) -> str:
    label = _TYPE_LABEL.get(f_type, "a threat indicator")
    clean_snippet = snippet.replace('"', "'")[:160]
    tier = "regex pattern matching" if method != "llm" else "the local qwen3:1.7b LLM"
    return (
        f"Deterministic {tier} identified '{value}' as {label}, "
        f"extracted from: \"{clean_snippet}\". "
        f"This indicator was flagged by the {tier.split()[0]} tier so the confidence score "
        f"reflects format/structural validity rather than semantic judgment. "
        f"Treat this as a reliable literal occurrence — cross-reference against other pages "
        f"in the same domain to determine whether it recurs, which substantially raises "
        f"its investigative significance."
    )


# ---------------------------------------------------------------------------
# Structured features → flat ExtractedEntityItem list
# ---------------------------------------------------------------------------

def _flatten_structured(
    structured: Dict[str, Any],
    loader: InMemoryTextLoader,
) -> List[ExtractedEntityItem]:
    """
    Convert the rich structured extraction output (product, vendor, reviews,
    catalog, sidebar) into the flat list of ExtractedEntityItem that the rest
    of the GUDAKESA pipeline (graph.py → persist) expects.

    Every item carries source_line_start/end so the frontend can highlight.
    """
    items: List[ExtractedEntityItem] = []
    page_type = structured.get("page_type", "GENERAL")

    # ── PRODUCT ──────────────────────────────────────────────────────────────
    product = structured.get("product") or {}
    if product.get("title"):
        prov = product.get("provenance") or {}
        line_start = prov.get("line_start")
        line_end = prov.get("line_end") or line_start
        prices = product.get("prices") or {}
        price_str = (
            prices.get("current") or prices.get("listed") or
            (f"${prices['range_low']}-${prices['range_high']}" if prices.get("range_low") else "")
        )
        context_str = f"Product: {product['title']}"
        if price_str:
            context_str += f" | Price: ${price_str}"
        if product.get("category"):
            context_str += f" | Category: {product['category']}"

        items.append(ExtractedEntityItem(
            feature_type="product",
            feature_value=product["title"],
            context=context_str[:250],
            description=(
                f"Dark-web product listing: '{product['title']}'. "
                + (f"Priced at ${price_str}. " if price_str else "")
                + (f"Category: {product.get('category', 'unknown')}. " )
                + (f"Rating: {product['overall_rating']}/5 ({product.get('review_count', 0)} reviews). "
                   if product.get("overall_rating") else "")
                + "Cross-reference vendor and reviews on this page to build the seller's profile."
            ),
            confidence_score=0.95,
            source_line_start=line_start,
            source_line_end=line_end,
            source_method=prov.get("method", "regex"),
            page_type=page_type,
            short_label="Dark-web product listing",
            category="activity",
            risk_level="low",
            tags=product.get("tags") or [],
        ))

    # ── VENDOR ───────────────────────────────────────────────────────────────
    vendor = structured.get("vendor") or {}
    if vendor.get("name"):
        prov = vendor.get("provenance") or {}
        line_start = prov.get("line_start")
        contacts = vendor.get("contacts") or {}

        items.append(ExtractedEntityItem(
            feature_type="username",
            feature_value=vendor["name"],
            context=f"Vendor/seller: {vendor['name']}"
                    + (f" | Rating: {vendor['rating']}/5" if vendor.get("rating") else ""),
            description=(
                f"Dark-web vendor/seller identity '{vendor['name']}' identified on this page. "
                + (f"Rated {vendor['rating']}/5 by buyers. " if vendor.get("rating") else "")
                + (f"Vendor type: {vendor.get('type', 'marketplace_vendor').replace('_', ' ')}. ")
                + "This handle is the primary anchor for cross-referencing this seller's activity "
                + "across multiple listings and domains."
            ),
            confidence_score=0.92,
            source_line_start=line_start,
            source_line_end=line_start,
            source_method=prov.get("method", "regex_vendor"),
            page_type=page_type,
            short_label="Vendor/seller handle",
            category="identity",
            risk_level="medium",
            actor_role="vendor",
            tags=["vendor", "seller-identity"],
        ))

        # Vendor contact details
        if contacts.get("email"):
            items.append(ExtractedEntityItem(
                feature_type="email",
                feature_value=contacts["email"],
                context=f"Vendor contact email for {vendor['name']}",
                description=_make_description("email", contacts["email"], f"Vendor: {vendor['name']}", "regex"),
                confidence_score=0.95,
                source_line_start=line_start,
                source_line_end=line_start,
                source_method="regex",
                page_type=page_type,
                short_label="Vendor contact email",
                category="communication",
                risk_level="medium",
                actor_role="vendor",
                related_indicators=[vendor["name"]],
            ))

        if contacts.get("telegram"):
            items.append(ExtractedEntityItem(
                feature_type="username",
                feature_value=contacts["telegram"],
                context=f"Telegram handle for vendor {vendor['name']}",
                description=_make_description("username", contacts["telegram"], f"Telegram: @{contacts['telegram']}", "regex"),
                confidence_score=0.90,
                source_line_start=line_start,
                source_line_end=line_start,
                source_method="regex",
                page_type=page_type,
                short_label="Vendor Telegram handle",
                category="communication",
                risk_level="medium",
                actor_role="vendor",
                related_indicators=[vendor["name"]],
            ))

        if contacts.get("jabber"):
            items.append(ExtractedEntityItem(
                feature_type="xmpp",
                feature_value=contacts["jabber"],
                context=f"XMPP/Jabber for vendor {vendor['name']}",
                description=_make_description("xmpp", contacts["jabber"], f"Jabber: {contacts['jabber']}", "regex"),
                confidence_score=0.90,
                source_line_start=line_start,
                source_line_end=line_start,
                source_method="regex",
                page_type=page_type,
                short_label="Vendor XMPP/Jabber",
                category="communication",
                risk_level="medium",
                actor_role="vendor",
                related_indicators=[vendor["name"]],
            ))

    # ── REVIEWS ──────────────────────────────────────────────────────────────
    reviews = structured.get("reviews") or []
    for rev in reviews:
        prov = rev.get("provenance") or {}
        author = rev.get("author", "Anonymous")
        if author.lower() in ("anonymous", "none", "n/a", ""):
            continue

        line_start = prov.get("line_start")
        line_end = prov.get("line_end") or line_start
        comment = (rev.get("comment") or "")[:200]
        context_str = (
            f"Review by {author}"
            + (f" [{rev['rating']}/5]" if rev.get("rating") else "")
            + (f" ({rev.get('date', '')})" if rev.get("date") else "")
            + f": {comment[:80]}"
        )

        items.append(ExtractedEntityItem(
            feature_type="review",
            feature_value=comment[:250] if comment else f"Review by {author}",
            context=context_str[:250],
            description=(
                f"Customer review submitted by '{author}'"
                + (f" rated {rev['rating']}/5" if rev.get("rating") else "")
                + (f" on {rev['date']}" if rev.get("date") and rev["date"] != "Unknown" else "")
                + f". Comment: \"{comment[:120]}\". "
                + "This reviewer is a likely buyer — cross-reference their username against other pages to build a buyer profile."
            ),
            confidence_score=prov.get("confidence", 0.88),
            source_line_start=line_start,
            source_line_end=line_end,
            source_method=prov.get("method", "regex_review"),
            page_type=page_type,
            short_label=f"Buyer review by {author}",
            category="activity",
            risk_level="low",
            actor_role="buyer",
            tags=["review", "buyer-feedback"],
        ))

        # Reviewer as a username identity
        items.append(ExtractedEntityItem(
            feature_type="username",
            feature_value=author,
            context=f"Reviewer username: {author}",
            description=(
                f"Reviewer identity '{author}' derived from a customer review. "
                + f"Has left at least one rating on this page. "
                + "Track this handle across other pages/domains to build a buyer profile."
            ),
            confidence_score=0.82,
            source_line_start=line_start,
            source_line_end=line_start,
            source_method=prov.get("method", "regex_review"),
            page_type=page_type,
            short_label=f"Buyer username: {author}",
            category="identity",
            risk_level="low",
            actor_role="buyer",
        ))

    # ── CATALOG PRODUCTS ─────────────────────────────────────────────────────
    catalog = structured.get("catalog_products") or []
    for cp in catalog:
        prov = cp.get("provenance") or {}
        title = cp.get("title", "")
        if not title:
            continue
        line_start = prov.get("line_start")
        items.append(ExtractedEntityItem(
            feature_type="product",
            feature_value=title,
            context=(
                f"Catalog listing: {title}"
                + (f" | ${cp['price']}" if cp.get("price") else "")
                + (f" | Vendor: {cp['vendor']}" if cp.get("vendor") else "")
            )[:250],
            description=(
                f"Dark-web catalog item '{title}' found on a listing/archive page. "
                + (f"Price: {cp.get('price', 'unknown')}. ")
                + (f"Vendor: {cp['vendor']}. " if cp.get("vendor") else "")
                + "Enumerate vendor for dossier build."
            ),
            confidence_score=prov.get("confidence", 0.85),
            source_line_start=line_start,
            source_line_end=line_start,
            source_method=prov.get("method", "regex_card"),
            page_type=page_type,
            short_label="Catalog product",
            category="activity",
            risk_level="low",
            tags=["catalog", "listing"],
        ))

    # ── REGEX SWEEP — crypto, onion, email, PGP across all page text ─────────
    text = loader.raw_text
    regex_hits = _regex_sweep(text, loader, page_type)
    items.extend(regex_hits)

    # ── SIDEBAR contacts / onion URLs ────────────────────────────────────────
    sidebar = structured.get("sidebar") or {}
    top_vendors = sidebar.get("top_vendors") or []
    for tv in top_vendors:
        name = tv.get("name", "")
        if name:
            items.append(ExtractedEntityItem(
                feature_type="username",
                feature_value=name,
                context=f"Top-rated vendor in sidebar: {name}"
                        + (f" [{tv['rating']}/5]" if tv.get("rating") else ""),
                description=(
                    f"'{name}' appears in the marketplace's 'Top Rated Vendors' sidebar widget, "
                    + "indicating a high-volume or well-reviewed seller on this platform."
                ),
                confidence_score=0.80,
                source_method="regex",
                page_type=page_type,
                short_label="Top-rated sidebar vendor",
                category="identity",
                risk_level="low",
                actor_role="vendor",
            ))

    return items


# ---------------------------------------------------------------------------
# Regex sweep — patterns from patterns.py across the full page text
# ---------------------------------------------------------------------------

_REGEX_SWEEPS: List[Tuple[str, Any, float]] = [
    ("onion_url", pat.ONION_DOMAIN, 0.95),
    ("email", pat.EMAIL_ADDR, 0.93),
    ("crypto_wallet", pat.BTC_ADDRESS, 0.97),
    ("crypto_wallet", pat.XMR_ADDRESS, 0.97),
    ("username", pat.TELEGRAM_HANDLE, 0.88),
    ("xmpp", pat.JABBER_XMPP, 0.90),
]

# PGP block pattern (not in patterns.py, add locally)
_PGP_BLOCK = re.compile(
    r"-----BEGIN PGP PUBLIC KEY BLOCK-----[\s\S]{50,}?-----END PGP PUBLIC KEY BLOCK-----",
)


def _regex_sweep(
    text: str,
    loader: InMemoryTextLoader,
    page_type: str,
) -> List[ExtractedEntityItem]:
    """Apply compiled regex patterns across the full page text."""
    items: List[ExtractedEntityItem] = []
    seen: set = set()

    for f_type, compiled_pat, score in _REGEX_SWEEPS:
        for m in compiled_pat.finditer(text):
            val = m.group(1) if m.groups() else m.group(0)
            val = val.strip()
            if not val or (f_type, val.lower()) in seen:
                continue
            seen.add((f_type, val.lower()))

            line_no = loader.char_offset_to_line(m.start())
            start = max(0, m.start() - 50)
            end = min(len(text), m.end() + 50)
            snippet = text[start:end].replace("\n", " ").strip()

            items.append(ExtractedEntityItem(
                feature_type=f_type,
                feature_value=val,
                context=snippet[:250],
                description=_make_description(f_type, val, snippet, "regex"),
                confidence_score=score,
                source_line_start=line_no,
                source_line_end=line_no,
                source_method="regex",
                page_type=page_type,
                short_label=f"{f_type.replace('_', ' ').title()} (pattern match)",
                category=CATEGORY_BY_TYPE.get(f_type, "other"),
                risk_level=RISK_BY_TYPE.get(f_type, "low"),
                tags=["regex", "deterministic-match"],
            ))

    # PGP blocks
    for m in _PGP_BLOCK.finditer(text):
        val = m.group(0).strip()
        if ("pgp_key", val.lower()[:40]) in seen:
            continue
        seen.add(("pgp_key", val.lower()[:40]))
        line_no = loader.char_offset_to_line(m.start())
        items.append(ExtractedEntityItem(
            feature_type="pgp_key",
            feature_value=val[:500],
            context="Full PGP public key block found on page",
            description=(
                f"An armored PGP public key block was detected on this page. "
                "PGP keys are a strong operational security signal — the key owner "
                "intentionally published it here for encrypted communications. "
                "Extract and import into a keyserver lookup to identify the owner."
            ),
            confidence_score=0.99,
            source_line_start=line_no,
            source_line_end=loader.char_offset_to_line(m.end()),
            source_method="regex",
            page_type=page_type,
            short_label="PGP public key block",
            category="identity",
            risk_level="medium",
            tags=["pgp", "opsec"],
        ))

    return items


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _dedupe(items: List[ExtractedEntityItem]) -> List[ExtractedEntityItem]:
    seen: dict = {}
    order: list = []
    for it in items:
        key = (it.feature_type.lower(), it.feature_value.lower()[:120])
        if key not in seen:
            seen[key] = it
            order.append(key)
        else:
            if (it.confidence_score or 0) > (seen[key].confidence_score or 0):
                seen[key] = it
    return [seen[k] for k in order]


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def extract_features_with_llm(text: str, filename: str = "page.txt") -> List[ExtractedEntityItem]:
    """
    Main extraction pipeline (replaces the old Gemini extractor).

    Strategy:
      1. Load text into InMemoryTextLoader (line indexing, boilerplate strip)
      2. Classify page type (PRODUCT_DETAIL | CATALOG_LISTING | GENERAL)
      3. Run structured regex extractors by page type
      4. Apply global regex sweep (crypto, onion, email, PGP)
      5. If feature count < threshold AND Ollama available → qwen3:1.7b fallback
      6. Flatten all structured data → List[ExtractedEntityItem]
      7. Deduplicate and return
    """
    if not text or not text.strip():
        return []

    loader = InMemoryTextLoader(text, filename=filename)
    page_type = classify_page(text)
    ollama_ok = is_ollama_available()

    # Build structured extraction by page type
    structured: Dict[str, Any] = {"page_type": page_type}

    if page_type == PageType.PRODUCT_DETAIL:
        structured["product"] = extract_product(loader)
        structured["reviews"] = extract_reviews(loader)
        structured["vendor"] = extract_vendor(loader)
        structured["catalog_products"] = []
    elif page_type == PageType.CATALOG_LISTING:
        structured["product"] = None
        structured["reviews"] = []
        structured["vendor"] = extract_vendor(loader)
        structured["catalog_products"] = extract_catalog(loader)
    else:  # GENERAL
        structured["product"] = extract_product(loader)
        structured["reviews"] = extract_reviews(loader)
        structured["vendor"] = extract_vendor(loader)
        structured["catalog_products"] = []

    structured["sidebar"] = extract_sidebar(loader)
    top_vendors = extract_top_vendors_sidebar(loader)
    if top_vendors:
        structured["sidebar"]["top_vendors"] = top_vendors

    feat_count = count_features(structured)

    # LLM fallback if regex yielded very little
    if feat_count < MIN_FEATURES_REGEX and ollama_ok:
        print(f"[Extractor] Low feature count ({feat_count}), running qwen3:1.7b fallback...")
        llm_data = llm_fallback_extract(loader)
        if not structured.get("product") and llm_data.get("product"):
            structured["product"] = llm_data["product"]
        if not structured.get("reviews") and llm_data.get("reviews"):
            structured["reviews"] = llm_data["reviews"]
        if not structured.get("vendor") and llm_data.get("vendor"):
            structured["vendor"] = llm_data["vendor"]

    # Generate summary
    try:
        structured["summary"] = summarize_page(loader, structured)
    except Exception:
        structured["summary"] = ""

    # Flatten structured → flat items
    items = _flatten_structured(structured, loader)
    items = _dedupe(items)

    print(
        f"[Extractor] Page type: {page_type} | "
        f"Structured features: {feat_count} | "
        f"Flat items: {len(items)} | "
        f"Ollama: {'ON' if ollama_ok else 'OFF'}"
    )

    return items