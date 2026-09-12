import os
import re
from typing import List
from dotenv import load_dotenv

load_dotenv()

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from .schemas import ExtractedFeatureBatch, ExtractedEntityItem


REGEX_PATTERNS = [
    ("email", r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', 0.95),
    ("email", r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.onion', 0.99),
    ("ip", r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', 0.90),
    ("crypto_wallet", r'\b(1|3)[a-km-zA-HJ-NP-Z1-9]{25,34}\b', 0.95),  # BTC Legacy/P2SH
    ("crypto_wallet", r'\bbc1[a-z0-9]{11,71}\b', 0.95),  # BTC Bech32
    ("crypto_wallet", r'\b4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}\b', 0.95),  # XMR Monero
    ("username", r'/(?:user|profile|vendor|member)/([a-zA-Z0-9_\-]+)', 0.85),
    ("username", r'@([a-zA-Z0-9_]{3,30})', 0.80),
]


def regex_fallback_extractor(text: str) -> List[ExtractedEntityItem]:
    """Fallback rule-based regex extraction when LLM API key is not set or API call fails."""
    extracted = []
    seen = set()

    for f_type, pattern, base_score in REGEX_PATTERNS:
        try:
            matches = re.finditer(pattern, text)
            for match in matches:
                val = match.group(1) if match.groups() else match.group(0)
                val = val.strip()
                if not val or val.lower() in seen or len(val) < 3:
                    continue
                seen.add(val.lower())

                start = max(0, match.start() - 40)
                end = min(len(text), match.end() + 40)
                snippet = text[start:end].replace('\n', ' ').strip()

                extracted.append(ExtractedEntityItem(
                    feature_type=f_type,
                    feature_value=val,
                    context=snippet,
                    description=f"Rule-based regex detected {f_type}",
                    confidence_score=base_score
                ))
        except Exception as e:
            print(f"[Regex Warning] {f_type} pattern error: {e}")

    return extracted


def extract_features_with_llm(text: str) -> List[ExtractedEntityItem]:
    """OpenRouter first, then Ollama (qwen3:1.7b), then regex."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    model_name = os.getenv("OPENROUTER_MODEL", "google/gemini-3.6-flash")

    if openrouter_key and not openrouter_key.startswith("your_") and openrouter_key.strip():
        try:
            llm = ChatOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key,
                model=model_name,
                temperature=0.1,
                max_tokens=2048,
                request_timeout=90,
                default_headers={
                    "HTTP-Referer": "https://gudakesa.intel",
                    "X-Title": "Gudakesa Threat De-anonymization"
                }
            )

            structured_llm = llm.with_structured_output(ExtractedFeatureBatch)
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", """You are an elite Cyber Threat Intelligence (CTI) AI agent specializing in dark web threat actor de-anonymization.
Extract: username, email, ip, crypto_wallet, post, review, product, other.
For each: feature_type, feature_value, context, description, confidence_score."""),
                ("human", "Scraped Dark Web Document Text:\n\n{text}")
            ])
            chain = prompt_template | structured_llm
            result: ExtractedFeatureBatch = chain.invoke({"text": text[:12000]})
            if result and result.features:
                return result.features
        except Exception as e:
            import traceback
            print(f"[AI Extractor ERROR] OpenRouter failed: {type(e).__name__}: {e}")
            print(f"[AI Extractor TRACE] {traceback.format_exc()}")

    print("[AI Extractor] Trying Ollama offline LLM fallback...")
    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        from .llm import get_ollama_llm, strip_think, parse_json_object

        ollama_llm = get_ollama_llm(temperature=0.1)
        if ollama_llm:
            result_msg = ollama_llm.invoke([
                SystemMessage(content="Extract threat intelligence JSON only. Schema: {\"features\":[{\"feature_type\":\"username|email|ip|crypto_wallet|post|product|review|other\",\"feature_value\":\"\",\"context\":\"\",\"description\":\"\",\"confidence_score\":0.8}]}"),
                HumanMessage(content=f"Text to analyze:\n\n{text[:6000]}"),
            ])
            parsed = parse_json_object(strip_think(getattr(result_msg, "content", "") or ""))
            if parsed and parsed.get("features"):
                items = []
                for f in parsed["features"]:
                    items.append(ExtractedEntityItem(
                        feature_type=f.get("feature_type", "other"),
                        feature_value=str(f.get("feature_value", "")),
                        context=str(f.get("context", "")),
                        description=str(f.get("description", "")),
                        confidence_score=float(f.get("confidence_score") or 0.8),
                    ))
                if items:
                    print(f"[AI Extractor] Ollama returned {len(items)} features.")
                    return items
    except Exception as ollama_err:
        print(f"[AI Extractor ERROR] Ollama also failed: {type(ollama_err).__name__}: {ollama_err}")

    # Tier 3: Regex fallback
    print("[AI Extractor] All LLMs unavailable. Using regex fallback.")
    return regex_fallback_extractor(text)
