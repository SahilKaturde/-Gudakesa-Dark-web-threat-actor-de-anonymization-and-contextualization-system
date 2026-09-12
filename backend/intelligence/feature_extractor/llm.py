"""
LLM module for GUDAKESA Intelligence Feature Extractor.
Gemini only, via Google AI Studio.

Env:
    GOOGLE_API_KEY  — required
"""
import os
import re
import json
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI

# ---------------------------------------------------------------------------
# Config — change here to swap models
# ---------------------------------------------------------------------------
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"   # try "gemini-3.8-flash" if your key has it

# ---------------------------------------------------------------------------
# Gemini factory
# ---------------------------------------------------------------------------
def get_gemini_llm(
    model: str = DEFAULT_GEMINI_MODEL,
    temperature: float = 0.6,
    max_tokens: int = 8192,
) -> Optional[ChatGoogleGenerativeAI]:
    """Return a Gemini client, or None if GOOGLE_API_KEY is missing."""
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[LLM] GOOGLE_API_KEY not set")
        return None

    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        max_output_tokens=max_tokens,
        google_api_key=api_key,
    )


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------
_THINK_PATTERNS = [
    re.compile(r"<think(?:ing)?>(.*?)</think(?:ing)?>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<reasoning>(.*?)</reasoning>", re.DOTALL | re.IGNORECASE),
]


def strip_think(text: str) -> str:
    if not text:
        return ""
    out = text
    for pat in _THINK_PATTERNS:
        out = pat.sub("", out)
    return out.strip()


def extract_reasoning(text: str) -> str:
    if not text:
        return ""
    chunks = []
    for pat in _THINK_PATTERNS:
        chunks.extend(m.strip() for m in pat.findall(text) if m.strip())
    return "\n".join(chunks).strip()


def parse_json_object(text: str) -> Optional[dict]:
    """Extract the first JSON object from a string, tolerating prose/fences."""
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        candidate = brace.group(0) if brace else None
    if not candidate:
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        try:
            last = candidate.rfind("}")
            return json.loads(candidate[: last + 1])
        except Exception:
            return None