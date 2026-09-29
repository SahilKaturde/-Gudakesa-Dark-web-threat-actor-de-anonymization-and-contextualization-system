"""
extractor/classifier.py
Accurate rule-based page classifier for darkweb marketplaces.
Distinguishes between PRODUCT_DETAIL, CATALOG_LISTING, and GENERAL.
"""
import re
from . import patterns


class PageType:
    PRODUCT_DETAIL = "PRODUCT_DETAIL"
    CATALOG_LISTING = "CATALOG_LISTING"
    GENERAL = "GENERAL"


def classify_page(text: str) -> str:
    """Classify a page based on structural darkweb signals."""
    lines = text.splitlines()
    first_line = lines[0] if lines else ""

    # Check for pagination or catalog grid markers
    has_showing_results = bool(patterns.SHOWING_RESULTS.search(text))
    has_archive_title = bool(
        "archives -" in first_line.lower() or
        "page of" in first_line.lower() or
        "marketplace -" in first_line.lower()
    )
    h1_catalog = bool(re.search(
        r"^#\s+(?:Marketplace|Shop|Archives|Guns|Rifle|Silencers|Ammunition|Drones|Explosives|Knives|Drugs)\s*$",
        text, re.MULTILINE | re.I
    ))

    if has_showing_results or (has_archive_title and h1_catalog):
        return PageType.CATALOG_LISTING

    # Check for General / FAQ / Contact / Directory
    if any(k in first_line.lower() for k in ["frequently asked questions", "contact us", "onion index"]):
        return PageType.GENERAL

    # Check for Product Detail cues
    h1_matches = patterns.H1_TITLE.findall(text)
    has_price = bool(patterns.PRICE_DOLLAR.search(text))
    has_add_to_cart = bool(patterns.ADD_TO_CART.search(text))
    has_breadcrumb = bool(patterns.BREADCRUMB.search(text))
    has_review_section = bool(patterns.REVIEW_SECTION_HEADER.search(text) or "add a review" in text.lower())
    has_category_label = bool(patterns.CATEGORY_LABEL.search(text))

    if h1_matches and has_price:
        first_h1 = h1_matches[0].strip().lower()
        if first_h1 not in ["marketplace", "shop", "your cart", "archives"]:
            if has_add_to_cart or has_breadcrumb or has_category_label or has_review_section:
                return PageType.PRODUCT_DETAIL

    if has_archive_title or (len(patterns.ARCHIVE_ITEM.findall(text)) >= 3):
        return PageType.CATALOG_LISTING

    if not has_price and not has_add_to_cart:
        return PageType.GENERAL

    return PageType.PRODUCT_DETAIL
