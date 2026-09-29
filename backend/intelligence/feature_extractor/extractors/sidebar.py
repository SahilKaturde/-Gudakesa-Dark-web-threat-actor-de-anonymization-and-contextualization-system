"""
extractor/extractors/sidebar.py
Extracts navigation categories, top-rated products, and recent customer activity.
"""
import re
from typing import Any, Dict, List
from .. import patterns
from ..loader import TextLoader


def _extract_section(text: str, header_pattern) -> str:
    """Extract text between a section header and the next ## header."""
    m = header_pattern.search(text)
    if not m:
        return ""
    start = m.end()
    nm = patterns.H2_SECTION.search(text[start:])
    if nm:
        return text[start:start + nm.start()]
    return text[start:]


def extract_categories(loader: TextLoader) -> List[str]:
    """Extract marketplace category names."""
    text = loader.raw_text
    categories = set()

    lines = loader.lines
    in_menu = False
    for line in lines[:40]:
        if "menu" in line.lower():
            in_menu = True
            continue
        if in_menu:
            if line.startswith("Search for:") or line.startswith("Home /") or line.startswith("# "):
                break
            stripped = line.strip().lstrip("*- ").strip()
            if stripped and stripped not in ["Home", "Shop", "Frequently Asked Questions", "Contact us", "View your cart +"]:
                categories.add(stripped)

    return sorted(categories)


def extract_recent_comments(loader: TextLoader) -> List[Dict[str, str]]:
    """Extract recent comments from sidebar widget."""
    section = _extract_section(loader.raw_text, patterns.RECENT_COMMENTS_HEADER)
    if not section:
        return []

    comments = []
    for m in patterns.RECENT_COMMENT_ITEM.finditer(section):
        comments.append({
            "username": m.group(1).strip(),
            "post_title": m.group(2).strip(),
        })
    return comments


def extract_sidebar(loader: TextLoader) -> Dict[str, Any]:
    """Extract sidebar metadata."""
    return {
        "categories": extract_categories(loader),
        "recent_comments": extract_recent_comments(loader),
    }
