"""
extractor/llm/client.py
Direct HTTP client for qwen3:1.7b via Ollama.
"""
import re
import logging
import requests
from ..config import (
    OLLAMA_GENERATE_URL, OLLAMA_TAGS_URL, OLLAMA_MODEL,
    LLM_TEMPERATURE, LLM_TOP_P, LLM_MAX_TOKENS, LLM_NUM_CTX,
    LLM_REQUEST_TIMEOUT,
)

log = logging.getLogger(__name__)


def is_ollama_available() -> bool:
    """Check if Ollama server is running and qwen3:1.7b is available."""
    try:
        r = requests.get(OLLAMA_TAGS_URL, timeout=3)
        if r.status_code == 200:
            models = [m.get("name", "") for m in r.json().get("models", [])]
            return any(OLLAMA_MODEL in m for m in models)
    except Exception:
        pass
    return False


def ask_qwen(prompt: str, max_tokens: int = None) -> str:
    """Query qwen3:1.7b with parameter-tailored micro-prompts."""
    if max_tokens is None:
        max_tokens = LLM_MAX_TOKENS

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": LLM_TEMPERATURE,
            "top_p": LLM_TOP_P,
            "num_predict": max_tokens,
            "num_ctx": LLM_NUM_CTX,
        },
    }

    try:
        resp = requests.post(
            OLLAMA_GENERATE_URL, json=payload, timeout=LLM_REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        result = resp.json().get("response", "")

        if "<think>" in result:
            result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL)
        return result.strip()
    except requests.exceptions.ConnectionError:
        log.debug("Ollama not reachable at %s", OLLAMA_GENERATE_URL)
    except requests.exceptions.Timeout:
        log.warning("Ollama query timed out")
    except Exception as exc:
        log.warning("Ollama error: %s", exc)

    return ""
