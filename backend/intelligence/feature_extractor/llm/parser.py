"""
extractor/llm/parser.py
Defensive JSON parser with multi-stage fallback for LLM outputs.
"""
import json
import re
import logging
from typing import Any, Optional, Union

log = logging.getLogger(__name__)


def parse_llm_json(raw: str) -> Optional[Union[dict, list]]:
    """Defensively extract and parse JSON from LLM generation."""
    if not raw or not raw.strip():
        return None

    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    for pat in [
        re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```"),
        re.compile(r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})"),
        re.compile(r"(\[[\s\S]*\])"),
    ]:
        m = pat.search(raw)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue

    cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
    cleaned = cleaned.replace("'", '"')
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    return None
