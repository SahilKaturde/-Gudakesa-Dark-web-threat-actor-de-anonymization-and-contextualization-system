"""
extractor/extractors/product.py
Extracts product titles, prices, descriptions, specifications, stock, and categories.
"""
import re
from typing import Any, Dict, List, Optional
from .. import patterns
from .base import make_provenance
from ..loader import TextLoader


def extract_product(loader: TextLoader) -> Optional[Dict[str, Any]]:
    """Extract structured product details from a product page."""
    text = loader.raw_text

    # --- 1. Product Title ---
    title = None
    title_line = None

    h1_match = patterns.H1_TITLE.search(text)
    if h1_match:
        candidate = h1_match.group(1).strip()
        if candidate.lower() not in ["guns", "shop", "your cart", "welcome", "frequently asked questions"]:
            title = candidate
            title_line = loader.char_offset_to_line(h1_match.start())

    if not title:
        bc_match = patterns.BREADCRUMB.search(text)
        if bc_match:
            crumbs = [c.strip() for c in bc_match.group(1).split("/") if c.strip()]
            if crumbs:
                title = crumbs[-1]
                title_line = loader.char_offset_to_line(bc_match.start())

    if not title and loader.lines:
        first = loader.lines[0].strip()
        suffix_m = patterns.SITE_TITLE_SUFFIX.search(first)
        if suffix_m:
            title = first[:suffix_m.start()].strip()
            title_line = 1

    if not title:
        return None

    # --- 2. Prices ---
    prices = {}
    curr_m = patterns.PRICE_CURRENT.search(text)
    if curr_m:
        prices["current"] = curr_m.group(1).replace(",", "")
    orig_m = patterns.PRICE_ORIGINAL.search(text)
    if orig_m:
        prices["original"] = orig_m.group(1).replace(",", "")

    if not prices:
        range_m = patterns.PRICE_RANGE.search(text)
        if range_m:
            prices["range_low"] = range_m.group(1).replace(",", "")
            prices["range_high"] = range_m.group(2).replace(",", "")
        else:
            dollar_matches = patterns.PRICE_DOLLAR.findall(text)
            if dollar_matches:
                prices["listed"] = dollar_matches[0].replace(",", "")

    btc_m = patterns.PRICE_BTC.search(text)
    if btc_m:
        prices["btc"] = btc_m.group(1)
    xmr_m = patterns.PRICE_XMR.search(text)
    if xmr_m:
        prices["xmr"] = xmr_m.group(1)

    # --- 3. Category & Breadcrumb ---
    category_path = None
    bc_match = patterns.BREADCRUMB.search(text)
    if bc_match:
        category_path = bc_match.group(1).strip()

    category = None
    cat_match = patterns.CATEGORY_LABEL.search(text)
    if cat_match:
        category = cat_match.group(1).strip()
    elif category_path:
        parts = [p.strip() for p in category_path.split("/") if p.strip()]
        if len(parts) >= 2:
            category = parts[-2]

    # --- 4. Tags, SKU & Availability ---
    tags = []
    tags_m = patterns.TAGS_LABEL.search(text)
    if tags_m:
        tags = [t.strip() for t in tags_m.group(1).split(",") if t.strip()]

    sku = None
    sku_m = patterns.SKU_LABEL.search(text)
    if sku_m:
        sku = sku_m.group(1).strip()

    availability = None
    avail_m = patterns.AVAILABILITY.search(text)
    if avail_m:
        availability = avail_m.group(1).strip()

    # --- 5. Ratings & Review Stats ---
    overall_rating = None
    review_count = None
    rating_match = patterns.RATING_BASED_ON.search(text)
    if rating_match:
        overall_rating = float(rating_match.group(1))
        review_count = int(rating_match.group(2))
    else:
        r2 = patterns.RATING_OVERALL.search(text)
        if r2:
            overall_rating = float(r2.group(1))
        rc = patterns.REVIEW_COUNT.search(text)
        if rc:
            review_count = int(rc.group(1))

    # --- 6. Specifications Table ---
    specs = {}
    for row_m in patterns.SPEC_TABLE_ROW.finditer(text):
        k = row_m.group(1).strip().rstrip("|").strip()
        v = row_m.group(2).strip().rstrip("|").strip()
        if not k.startswith("---") and not v.startswith("---") and k and v:
            specs[k] = v

    # --- 7. Description Snippet ---
    desc_snippet = ""
    if title_line:
        core_lines = loader.get_lines(title_line + 1, title_line + 16)
        desc_text = "\n".join(core_lines).strip()
        desc_text = re.sub(r"\$[0-9,.]+", "", desc_text)
        desc_text = re.sub(r"Add to cart.*", "", desc_text, flags=re.I)
        desc_text = desc_text.strip()
        if len(desc_text) > 300:
            desc_snippet = desc_text[:300] + "..."
        else:
            desc_snippet = desc_text

    # --- 8. Related Products on Page ---
    related_products = []
    rel_header = patterns.RELATED_PRODUCTS_HEADER.search(text)
    if rel_header:
        rel_section = text[rel_header.end():]
        for m in patterns.ARCHIVE_ITEM.finditer(rel_section):
            cat, rtitle, rprice = m.groups()
            related_products.append({
                "title": rtitle.strip(),
                "category": cat.strip(),
                "price": f"${rprice}",
            })

    return {
        "title": title,
        "prices": prices,
        "category_path": category_path,
        "category": category,
        "tags": tags,
        "sku": sku,
        "availability": availability,
        "overall_rating": overall_rating,
        "review_count": review_count,
        "specs": specs if specs else None,
        "description_snippet": desc_snippet if desc_snippet else None,
        "related_products": related_products if related_products else None,
        "provenance": make_provenance(
            loader.filename,
            line_start=title_line,
            line_end=title_line,
            method="regex",
        ),
    }
