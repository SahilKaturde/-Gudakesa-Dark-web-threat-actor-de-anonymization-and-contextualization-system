"""
AI Chat module for GUDAKESA Intelligence Feature Extractor.
Primary: OpenRouter (google/gemini-3.6-flash)
Fallback: Ollama (qwen3:1.7b) for offline operation
"""
from typing import List, Dict, Optional

from .llm import invoke_with_fallback

GRAPH_KEYWORDS = ["graph", "chart", "plot", "visualize", "visualisation", "bar chart", "pie chart", "diagram", "distribution"]

CHAT_SYSTEM_PROMPT = """You are GUDAKESA, an elite Cyber Threat Intelligence (CTI) AI analyst specializing in dark web threat actor de-anonymization and investigation.

You have access to:
- Scraped dark web document content (raw page text from .onion sites, forums, markets)
- Extracted threat intelligence indicators (emails, usernames, crypto wallets, IPs, etc.)

Your capabilities:
1. Answer analyst questions about document content and extracted features
2. Identify patterns, threat actor behaviors, and connections between indicators
3. Summarize threats, assess risk, and suggest investigative leads
4. When asked for a graph/visualization, respond naturally and the system will auto-generate one

Keep responses concise, professional, and intelligence-focused. Use CTI terminology.
"""


def _build_context_block(page_text: str, features: List[Dict]) -> str:
    """Build a structured context block for the LLM."""
    feature_lines = ""
    if features:
        by_type: Dict[str, List[str]] = {}
        for f in features:
            ft = f.get("feature_type", "other")
            fv = f.get("feature_value", "")
            by_type.setdefault(ft, []).append(fv)
        feature_lines = "\n".join(
            f"  [{k.upper()}] ({len(v)} found): {', '.join(v[:5])}" + (" ..." if len(v) > 5 else "")
            for k, v in by_type.items()
        )
    else:
        feature_lines = "  (none extracted yet — use Extract Feature button)"

    doc_snippet = page_text[:4000].strip() if page_text else "(no document loaded)"

    return f"""=== DOCUMENT CONTENT (truncated to 4000 chars) ===
{doc_snippet}

=== EXTRACTED THREAT INDICATORS ({len(features)} total) ===
{feature_lines}
"""


def _fallback_response(message: str, features: List[Dict], page_text: str) -> str:
    """Rule-based fallback when both LLMs are unavailable."""
    msg = message.lower()
    if not features:
        return (
            "No features have been extracted yet. Click the **⚡ Extract Feature** button "
            "to run AI analysis on this document first, then I can answer questions about it."
        )

    by_type: Dict[str, List[str]] = {}
    for f in features:
        by_type.setdefault(f.get("feature_type", "other"), []).append(f.get("feature_value", ""))

    if any(k in msg for k in ["count", "how many", "total", "number"]):
        lines = [f"  • {k}: {len(v)}" for k, v in by_type.items()]
        return f"**Extracted {len(features)} indicators:**\n" + "\n".join(lines)

    if "email" in msg:
        vals = by_type.get("email", [])
        return f"**{len(vals)} email(s) found:** {', '.join(vals[:8]) or 'none'}"

    if any(k in msg for k in ["crypto", "wallet", "bitcoin", "btc", "xmr", "monero"]):
        vals = by_type.get("crypto_wallet", [])
        return f"**{len(vals)} crypto wallet(s) found:** {', '.join(vals[:3]) or 'none'}"

    if any(k in msg for k in ["username", "user", "handle", "alias", "vendor"]):
        vals = by_type.get("username", [])
        return f"**{len(vals)} username(s) found:** {', '.join(vals[:8]) or 'none'}"

    if any(k in msg for k in ["ip", "address", "server"]):
        vals = by_type.get("ip", [])
        return f"**{len(vals)} IP address(es) found:** {', '.join(vals[:8]) or 'none'}"

    summary = " | ".join(f"{k}: {len(v)}" for k, v in by_type.items())
    return (
        f"⚠️ AI services unavailable (OpenRouter + Ollama both offline). "
        f"Current indicators: {summary}. "
        f"Document size: {len(page_text)} chars."
    )


def chat_with_ai(
    message: str,
    page_text: str = "",
    features: Optional[List[Dict]] = None,
    history: Optional[List[Dict]] = None,
) -> Dict:
    """
    Main chat function. Tries OpenRouter → Ollama → rule-based fallback.
    Returns: {response: str, wants_graph: bool, llm_used: str}
    """
    features = features or []
    history = history or []

    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

    context = _build_context_block(page_text, features)
    wants_graph = any(kw in message.lower() for kw in GRAPH_KEYWORDS) and len(features) > 0

    messages = [SystemMessage(content=CHAT_SYSTEM_PROMPT + "\n\n" + context)]

    # Include last 8 turns of history
    for msg in history[-8:]:
        if msg.get("sender") == "user":
            messages.append(HumanMessage(content=msg["text"]))
        elif msg.get("sender") == "agent":
            messages.append(AIMessage(content=msg["text"]))

    messages.append(HumanMessage(content=message))

    text, provider = invoke_with_fallback(messages, temperature=0.4, max_tokens=1024)
    if text:
        return {"response": text, "wants_graph": wants_graph, "llm_used": provider}

    # --- Rule-based fallback ---
    return {
        "response": _fallback_response(message, features, page_text),
        "wants_graph": wants_graph,
        "llm_used": "fallback",
    }
