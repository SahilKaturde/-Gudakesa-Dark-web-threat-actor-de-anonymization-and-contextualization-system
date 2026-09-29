"""
extractor/extractors/catalog.py
Extracts product items from catalog grids and archive pages.
Filters out review headings, inquiries, and UI widgets to prevent false products.
"""
import re
from typing import Any, Dict, List
from .. import patterns
from .base import make_provenance
from ..loader import TextLoader

_EXCLUDE_TITLES = {
    "marketplace", "related products", "browse", "reviews",
    "cart", "product categories", "top rated vendors",
    "recent comments", "product tags", "recent posts",
    "general inquiries", "tags", "guns", "shop", "silencers",
    "ammunition", "rifle", "drones", "explosives", "rocket launcher",
    "want to chat?", "social", "home", "checkout", "view your cart +",
    "more offers", "store policies", "inquiries", "description"
}


def _is_invalid_title(title: str) -> bool:
    """Check if a title string is actually a heading or review section."""
    if not title:
        return True
    t = title.strip().lower()
    if t in _EXCLUDE_TITLES:
        return True
    if re.search(r"\d+\s+reviews?\s+for", t):
        return True
    if t.endswith("reviews") or t.startswith("reviews ("):
        return True
    if t.startswith("**") and t.endswith("**"):
        return True
    if len(t) < 3:
        return True
    return False


def extract_catalog(loader: TextLoader) -> List[Dict[str, Any]]:
    """Extract product cards from a catalog/archive page."""
    text = loader.raw_text
    products = []
    seen_titles = set()

    for match in patterns.ARCHIVE_ITEM.finditer(text):
        category, title, price = match.groups()
        title_clean = title.strip()
        if _is_invalid_title(title_clean) or title_clean in seen_titles:
            continue

        seen_titles.add(title_clean)
        line_start = loader.char_offset_to_line(match.start())

        products.append({
            "title": title_clean,
            "category": category.strip(),
            "price": f"${price.replace(',', '')}",
            "provenance": make_provenance(
                loader.filename, line_start=line_start, method="regex_archive"
            ),
        })

    for match in patterns.CATALOG_ITEM.finditer(text):
        title, rating, price, vendor, vrating = match.groups()
        title_clean = title.strip()
        if _is_invalid_title(title_clean) or title_clean in seen_titles:
            continue

        if not price and not vendor and not rating:
            continue

        seen_titles.add(title_clean)
        line_start = loader.char_offset_to_line(match.start())

        prod_item = {
            "title": title_clean,
            "rating": float(rating) if rating else None,
            "price": price.strip() if price else None,
            "vendor": vendor.strip() if vendor else None,
            "provenance": make_provenance(
                loader.filename, line_start=line_start, method="regex_card"
            ),
        }
        products.append(prod_item)

    return products
