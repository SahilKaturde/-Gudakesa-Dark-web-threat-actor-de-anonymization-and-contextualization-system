"""
AI Chat module for GUDAKESA Intelligence Feature Extractor.
Gemini only. Persistent memory (SQLite) with semantic recall.
"""
from typing import List, Dict, Optional

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from .llm import (
    get_gemini_llm,
    strip_think,
    extract_reasoning,
    DEFAULT_GEMINI_MODEL,
)
from .graphs import (
    generate_custom_bar_chart,
    generate_custom_pie_chart,
    generate_custom_confidence_chart,
)
from .memory import (
    init_memory_db,
    store_message,
    get_session_history,
    search_similar,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MAX_TOKENS = 8192
DOC_CHARS = 40000
HISTORY_TURNS = 20
HISTORY_CHARS = 4000
RECALL_TOP_K = 4

GRAPH_KEYWORDS = [
    "graph", "chart", "plot", "visualize", "visualisation",
    "bar chart", "pie chart", "diagram", "distribution",
]

CHAT_SYSTEM_PROMPT = """You are GUDAKESA, an elite Cyber Threat Intelligence (CTI) analyst specializing in dark web threat actor de-anonymization and investigation.

You have access to:
- Scraped dark web document content (raw page text from .onion sites, forums, markets)
- Extracted threat intelligence indicators (emails, usernames, crypto wallets, IPs, etc.)
- Persistent memory of prior analyst conversations (see RECALLED CONTEXT block when present)

REASONING PROTOCOL — follow this before every answer:
1. Silently parse the analyst's question and identify exactly what is being asked.
2. Locate the relevant evidence in the DOCUMENT CONTENT and EXTRACTED THREAT INDICATORS blocks.
3. Cross-reference indicators against prior conversation turns and RECALLED CONTEXT to detect links, aliases, and shared infrastructure.
4. Only then compose the final answer.

CAPABILITIES:
1. Answer thoroughly with exact names, prices, handles, and details from the document. Never stop mid-sentence.
2. Identify patterns, actor behaviors, and connections across indicators and history.
3. Summarize threats, assess risk, and suggest concrete investigative leads.
4. Visualization — you have THREE chart tools:
   - `generate_chart`           : vertical bar — comparing prices, counts, magnitudes
   - `generate_pie_chart`       : pie — proportions/composition of a total
   - `generate_confidence_chart`: horizontal bar — confidence scores or 0–1 metrics
   Call a tool ONLY when the analyst explicitly asks for a chart/graph/plot/visualization.

CRITICAL RULES:
- NEVER output placeholders like 'Analysis complete.' or truncate mid-sentence.
- If evidence is insufficient, say precisely what is missing and what to scrape next.
- Cite the source of each claim: [DOC], [EMAIL], [CRYPTO_WALLET], [USERNAME], [IP], [ONION_URL], [RECALL].
- Maintain full context from prior turns — treat the conversation as a live investigation.
"""


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@tool
def generate_chart(
    labels: List[str],
    values: List[float],
    title: str,
    x_label: str = "",
    y_label: str = "",
) -> str:
    """Generate a vertical bar chart. Use for comparing prices, counts, or magnitudes across categories."""
    return generate_custom_bar_chart(labels, values, title, x_label, y_label)


@tool
def generate_pie_chart(
    labels: List[str],
    values: List[float],
    title: str,
) -> str:
    """Generate a pie chart. Use for showing proportions or composition of a total (percentages)."""
    return generate_custom_pie_chart(labels, values, title)


@tool
def generate_confidence_chart(
    labels: List[str],
    values: List[float],
    title: str,
    x_label: str = "Confidence Score",
) -> str:
    """Generate a horizontal bar chart for confidence scores or other 0–1 metrics."""
    return generate_custom_confidence_chart(labels, values, title, x_label)


CHART_TOOLS = [generate_chart, generate_pie_chart, generate_confidence_chart]


# ---------------------------------------------------------------------------
# Context builders
# ---------------------------------------------------------------------------
def _build_context_block(page_text: str, features: List[Dict]) -> str:
    if features:
        by_type: Dict[str, List[str]] = {}
        for f in features:
            ft = f.get("feature_type", "other")
            fv = f.get("feature_value", "")
            if fv:
                by_type.setdefault(ft, []).append(fv)
        feature_lines = "\n".join(
            f"  [{k.upper()}] ({len(v)} found): "
            + ", ".join(v[:12])
            + (f" … (+{len(v) - 12} more)" if len(v) > 12 else "")
            for k, v in by_type.items()
        )
    else:
        feature_lines = "  (none extracted yet — use Extract Feature button)"

    doc_snippet = page_text[:DOC_CHARS].strip() if page_text else "(no document loaded)"
    truncated_marker = (
        f"\n\n[... {len(page_text) - DOC_CHARS} more chars omitted ...]"
        if page_text and len(page_text) > DOC_CHARS else ""
    )

    return (
        f"=== DOCUMENT CONTENT ({len(page_text)} chars total, "
        f"showing up to {DOC_CHARS}) ===\n"
        f"{doc_snippet}{truncated_marker}\n\n"
        f"=== EXTRACTED THREAT INDICATORS ({len(features)} total) ===\n"
        f"{feature_lines}\n"
    )


def _build_recall_block(recalls: List[Dict]) -> str:
    """Format semantic-search hits from prior sessions."""
    if not recalls:
        return ""
    lines = []
    for r in recalls:
        snippet = (r.get("text") or "").replace("\n", " ").strip()[:280]
        sid = (r.get("session_id") or "")[:8]
        score = r.get("score", 0.0)
        role = r.get("sender", "?")
        lines.append(f"  [{sid} · {role} · {score:.2f}] {snippet}")
    return (
        "=== RECALLED CONTEXT (from prior sessions, semantic match) ===\n"
        + "\n".join(lines) + "\n"
    )


def _history_to_messages(history: List[Dict]) -> List:
    out = []
    for msg in history[-HISTORY_TURNS:]:
        sender = msg.get("sender")
        text = (msg.get("text") or "")[:HISTORY_CHARS]
        if not text:
            continue
        if sender == "user":
            out.append(HumanMessage(content=text))
        elif sender == "agent":
            out.append(AIMessage(content=text))
    return out


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------
def _coerce_lv(args: Dict):
    labels = args.get("labels", []) or []
    raw_values = args.get("values") or []
    try:
        values = [float(v) for v in raw_values]
    except (TypeError, ValueError):
        return None, None
    if not labels or not values or len(labels) != len(values):
        return None, None
    return labels, values


def _dispatch_chart_tool(tool_name: str, args: Dict) -> Optional[str]:
    labels, values = _coerce_lv(args)
    if not labels:
        return None

    if tool_name == "generate_chart":
        return generate_custom_bar_chart(
            labels=labels, values=values,
            title=args.get("title", "Comparison"),
            x_label=args.get("x_label", ""),
            y_label=args.get("y_label", ""),
        )
    if tool_name == "generate_pie_chart":
        return generate_custom_pie_chart(
            labels=labels, values=values,
            title=args.get("title", "Distribution"),
        )
    if tool_name == "generate_confidence_chart":
        return generate_custom_confidence_chart(
            labels=labels, values=values,
            title=args.get("title", "Confidence by Category"),
            x_label=args.get("x_label", "Confidence Score"),
        )
    return None


def _run_chart_tools(response) -> Optional[str]:
    for tc in (getattr(response, "tool_calls", None) or []):
        png = _dispatch_chart_tool(tc.get("name"), tc.get("args", {}) or {})
        if png:
            return png
    return None


# ---------------------------------------------------------------------------
# Response finalizer
# ---------------------------------------------------------------------------
def _finalize(response, wants_graph: bool) -> Dict:
    raw = getattr(response, "content", "") or ""
    reasoning = extract_reasoning(raw)
    answer = strip_think(raw)

    ak = getattr(response, "additional_kwargs", {}) or {}
    side = ak.get("reasoning_content") or ak.get("reasoning") or ""
    if side:
        reasoning = (reasoning + "\n" + side).strip()

    graph_base64 = _run_chart_tools(response) if wants_graph else None

    if not answer:
        answer = (
            "Here is the requested visualization based on the document data:"
            if graph_base64
            else "I reviewed the document but need a more specific question. "
                 "Which actor, product, or indicator should I investigate?"
        )

    return {
        "response": answer,
        "reasoning": reasoning,
        "wants_graph": wants_graph,
        "llm_used": f"gemini:{DEFAULT_GEMINI_MODEL}",
        "graph_base64": graph_base64,
    }


def _error_response(features: List[Dict], page_text: str, err: str) -> Dict:
    by_type: Dict[str, List[str]] = {}
    for f in features:
        by_type.setdefault(f.get("feature_type", "other"), []).append(
            f.get("feature_value", "")
        )
    summary = " | ".join(f"{k}: {len(v)}" for k, v in by_type.items()) if by_type else "none"
    return {
        "response": (
            f"⚠️ **Gemini unavailable** — {err[:200]}\n\n"
            f"Extracted indicators: {summary}\n"
            f"Document size: {len(page_text)} chars."
        ),
        "reasoning": "",
        "wants_graph": False,
        "llm_used": "error",
        "graph_base64": None,
    }


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------
def chat_with_ai(
    message: str,
    page_text: str = "",
    features: Optional[List[Dict]] = None,
    history: Optional[List[Dict]] = None,
    session_id: Optional[str] = None,
) -> Dict:
    """
    Chat with Gemini. If session_id is provided, messages are persisted to
    SQLite and prior-session semantic recall is injected as extra context.
    """
    features = features or []
    history = history or []

    # --- Merge persistent history with client-supplied history ---
    merged_history: List[Dict] = []
    if session_id:
        try:
            persisted = get_session_history(session_id, limit=HISTORY_TURNS)
            merged_history.extend(persisted)
        except Exception as e:
            print(f"[Chat] Persistent history load failed: {str(e)[:140]}")
    merged_history.extend(history)

    # --- Cross-session semantic recall ---
    recalls: List[Dict] = []
    if session_id:
        try:
            recalls = search_similar(
                query=message,
                exclude_session=session_id,
                top_k=RECALL_TOP_K,
            )
        except Exception as e:
            print(f"[Chat] Recall failed: {str(e)[:140]}")

    # --- Build message stack ---
    context = _build_context_block(page_text, features)
    recall_block = _build_recall_block(recalls)

    system_content = CHAT_SYSTEM_PROMPT + "\n\n" + context
    if recall_block:
        system_content += "\n" + recall_block

    messages = [SystemMessage(content=system_content)]
    messages.extend(_history_to_messages(merged_history))
    messages.append(HumanMessage(content=message))

    wants_graph = any(kw in message.lower() for kw in GRAPH_KEYWORDS)

    llm = get_gemini_llm(temperature=0.6, max_tokens=MAX_TOKENS)
    if not llm:
        return _error_response(features, page_text, "GOOGLE_API_KEY not set")

    # --- Persist the user turn BEFORE calling the LLM so it's not lost on failure ---
    if session_id:
        try:
            store_message(session_id, "user", message)
        except Exception:
            pass

    try:
        if wants_graph:
            response = llm.bind_tools(CHART_TOOLS).invoke(messages)
        else:
            response = llm.invoke(messages)
        result = _finalize(response, wants_graph)

    except Exception as e:
        print(f"[LLM] Gemini failed: {str(e)[:240]}")
        return _error_response(features, page_text, f"{type(e).__name__}: {e}")

    # --- Persist the assistant turn ---
    if session_id and result.get("response"):
        try:
            store_message(session_id, "agent", result["response"])
        except Exception:
            pass

    # --- Attach recall metadata for UI (optional) ---
    if recalls:
        result["recalled"] = [
            {"session_id": r["session_id"], "score": r["score"]}
            for r in recalls
        ]

    return result


# Ensure the DB exists as soon as this module is imported
try:
    init_memory_db()
except Exception as _e:
    print(f"[Memory] Auto-init failed: {str(_e)[:160]}")