"""
extractor/extractors/review.py
Extracts individual customer reviews with user identification, rating, date, and comment.
"""
import re
from typing import Any, Dict, List
from .. import patterns
from .base import make_provenance
from ..loader import TextLoader


def _clean_username(raw: str) -> str:
    """Clean username from markdown bolding and whitespace."""
    if not raw:
        return "Anonymous"
    u = raw.strip()
    u = re.sub(r"^\*+", "", u)
    u = re.sub(r"\*+$", "", u)
    u = u.strip()
    return u if u else "Anonymous"


def extract_reviews(loader: TextLoader) -> List[Dict[str, Any]]:
    """Extract customer reviews from page."""
    text = loader.raw_text
    reviews = []
    seen_hashes = set()

    for match in patterns.REVIEW_ITEM_PATTERN.finditer(text):
        num_str, rating_str, author_raw, date_str, comment_raw = match.groups()

        author = _clean_username(author_raw)
        comment = comment_raw.strip()

        for marker in ["Add a review", "Cancel reply", "Your email", "Your rating", "Save my name"]:
            idx = comment.find(marker)
            if idx != -1:
                comment = comment[:idx].strip()

        if not comment:
            comment = "(no comment text)"

        rev_hash = f"{author}_{date_str}_{rating_str}"
        if rev_hash in seen_hashes:
            continue
        seen_hashes.add(rev_hash)

        line_start = loader.char_offset_to_line(match.start())
        line_end = loader.char_offset_to_line(match.end())

        reviews.append({
            "author": author,
            "rating": float(rating_str) if rating_str else None,
            "date": date_str.strip() if date_str else "Unknown",
            "comment": comment,
            "provenance": make_provenance(
                loader.filename,
                line_start=line_start,
                line_end=line_end,
                method="regex_review",
            ),
        })

    if not reviews:
        for match in patterns.SIMPLE_REVIEW_PATTERN.finditer(text):
            author_raw, date_str, rating_str, comment_raw = match.groups()
            author = _clean_username(author_raw)
            if not author or author.lower() in ["anonymous", "none", "n/a"]:
                continue

            comment = comment_raw.strip()[:300]
            for marker in ["Add a review", "## "]:
                idx = comment.find(marker)
                if idx != -1:
                    comment = comment[:idx].strip()

            rev_hash = f"{author}_{date_str}_{rating_str}"
            if rev_hash in seen_hashes:
                continue
            seen_hashes.add(rev_hash)

            line_start = loader.char_offset_to_line(match.start())
            line_end = loader.char_offset_to_line(match.end())

            reviews.append({
                "author": author,
                "rating": float(rating_str) if rating_str else None,
                "date": date_str.strip() if date_str else "Unknown",
                "comment": comment if comment else "(no comment text)",
                "provenance": make_provenance(
                    loader.filename,
                    line_start=line_start,
                    line_end=line_end,
                    method="regex_simple_review",
                ),
            })

    return reviews
