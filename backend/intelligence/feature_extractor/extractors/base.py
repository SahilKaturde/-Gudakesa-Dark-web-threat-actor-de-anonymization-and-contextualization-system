"""
extractor/extractors/base.py
Provenance tracking for extracted intelligence.
"""
from typing import Any, Dict, Optional


def make_provenance(
    filename: str,
    line_start: Optional[int] = None,
    line_end: Optional[int] = None,
    method: str = "regex",
    confidence: float = 0.9,
) -> Dict[str, Any]:
    """Create a provenance record with line-level traceability."""
    prov = {
        "file": filename,
        "method": method,
        "confidence": confidence,
    }
    if line_start is not None:
        prov["line_start"] = line_start
    if line_end is not None:
        prov["line_end"] = line_end
    return prov
