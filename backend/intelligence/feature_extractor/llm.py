"""Shared LLM helpers: OpenRouter first, then ChatOllama (qwen3:1.7b)."""
import json
import os
import re
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)


def strip_think(text: str) -> str:
    if not text:
        return ""
    return _THINK_RE.sub("", text).strip()


def parse_json_object(text: str) -> Optional[dict]:
    raw = strip_think(text or "")
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    raw = raw.strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(raw[start : end + 1])
                return data if isinstance(data, dict) else None
            except Exception:
                return None
    return None


def get_openrouter_llm(temperature: float = 0.4, max_tokens: int = 1024, timeout: int = 60):
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key or key.startswith("your_") or not key.strip():
        return None
    try:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=key,
            model=os.getenv("OPENROUTER_MODEL", "google/gemini-3.6-flash"),
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=timeout,
            default_headers={
                "HTTP-Referer": "https://gudakesa.intel",
                "X-Title": "Gudakesa CTI",
            },
        )
    except Exception as e:
        print(f"[LLM] OpenRouter init failed: {e}")
        return None


def get_ollama_llm(temperature: float = 0.4):
    try:
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "qwen3:1.7b"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=temperature,
        )
    except Exception as e:
        print(f"[LLM] Ollama init failed: {e}")
        return None


def invoke_with_fallback(messages, temperature: float = 0.4, max_tokens: int = 1024):
    """
    Invoke OpenRouter, then Ollama. Returns (text, provider) or (None, None).
    """
    llm = get_openrouter_llm(temperature=temperature, max_tokens=max_tokens)
    if llm:
        try:
            result = llm.invoke(messages)
            return strip_think(getattr(result, "content", "") or ""), "openrouter"
        except Exception as e:
            print(f"[LLM] OpenRouter invoke failed: {type(e).__name__}: {e}")

    llm = get_ollama_llm(temperature=temperature)
    if llm:
        try:
            result = llm.invoke(messages)
            return strip_think(getattr(result, "content", "") or ""), "ollama"
        except Exception as e:
            print(f"[LLM] Ollama invoke failed: {type(e).__name__}: {e}")

    return None, None
