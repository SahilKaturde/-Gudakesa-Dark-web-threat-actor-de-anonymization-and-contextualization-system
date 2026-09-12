"""
Investigation Report generation for GUDAKESA.
Gemini-only. Falls back to a data-driven report if Gemini is unavailable or
returns invalid JSON.
"""
import datetime
from typing import List, Dict
from collections import Counter
from dotenv import load_dotenv

from langchain_core.messages import SystemMessage, HumanMessage

from .llm import get_gemini_llm, parse_json_object, DEFAULT_GEMINI_MODEL

load_dotenv()


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
REPORT_SYSTEM_PROMPT = """You are a senior Cyber Threat Intelligence analyst writing a formal investigation report.
Generate a detailed CTI report for a dark web investigation. Be professional, precise and use CTI terminology.
Your output MUST be valid JSON matching EXACTLY the schema provided — no markdown, no backticks, no prose around it.
Return ONLY the raw JSON object."""

REPORT_SCHEMA_DESCRIPTION = """{
  "executive_summary": "2-3 sentence summary of findings",
  "threat_level": "CRITICAL | HIGH | MEDIUM | LOW | INFORMATIONAL",
  "threat_level_rationale": "1-2 sentence explanation of threat level",
  "key_findings": ["finding 1", "finding 2", "..."],
  "threat_actor_profile": {
    "likely_motivation": "...",
    "operational_security": "...",
    "estimated_sophistication": "Nation-State | Advanced | Intermediate | Low-Level",
    "indicators_of_attribution": ["indicator 1", "..."]
  },
  "ioc_analysis": {
    "high_value": ["IOC value 1", "..."],
    "notes": "Analysis notes on the IOCs"
  },
  "attack_vectors": ["vector 1", "..."],
  "recommendations": ["action 1", "..."],
  "investigative_leads": ["lead 1", "..."]
}"""


# ---------------------------------------------------------------------------
# Fallback report builder (no LLM)
# ---------------------------------------------------------------------------
def _fallback_report(features: List[Dict], page_text: str) -> Dict:
    """Build a structured report from extracted data without an LLM."""
    by_type = Counter(f.get("feature_type", "other") for f in features)
    high_conf = [f for f in features if (f.get("confidence_score") or 0) >= 0.85]
    has_crypto = by_type.get("crypto_wallet", 0) > 0
    has_email = by_type.get("email", 0) > 0
    has_pgp = by_type.get("pgp_key", 0) > 0

    threat_level = "INFORMATIONAL"
    if len(features) > 20 or has_crypto or has_pgp:
        threat_level = "HIGH"
    elif len(features) > 10:
        threat_level = "MEDIUM"
    elif len(features) > 0:
        threat_level = "LOW"

    key_findings: List[str] = []
    if has_crypto:
        key_findings.append(
            f"Cryptocurrency wallets detected ({by_type['crypto_wallet']}), "
            f"indicating financial transaction activity."
        )
    if has_email:
        key_findings.append(
            f"Email addresses identified ({by_type['email']}), "
            f"potentially linked to threat actor communications."
        )
    if by_type.get("username", 0):
        key_findings.append(
            f"Forum usernames/aliases extracted ({by_type['username']}), "
            f"useful for cross-platform correlation."
        )
    if by_type.get("ip", 0):
        key_findings.append(
            f"IP addresses present ({by_type['ip']}), may indicate "
            f"infrastructure or server hosting."
        )
    if has_pgp:
        key_findings.append(
            f"PGP public keys found ({by_type['pgp_key']}), strong identity "
            f"anchor for attribution."
        )
    if by_type.get("onion_url", 0):
        key_findings.append(
            f"Onion URLs extracted ({by_type['onion_url']}), useful for "
            f"infrastructure mapping."
        )
    if not key_findings:
        key_findings = ["Document analyzed. Insufficient pattern matches for automated key findings."]

    return {
        "executive_summary": (
            f"Analysis of the target document identified {len(features)} threat indicators "
            f"across {len(by_type)} categories. "
            + ("Cryptocurrency activity and " if has_crypto else "")
            + (
                "communication identifiers suggest active threat actor operations."
                if features else "No high-confidence indicators were found."
            )
        ),
        "threat_level": threat_level,
        "threat_level_rationale": (
            f"Based on {len(features)} extracted indicators across "
            f"{len(by_type)} categories."
        ),
        "key_findings": key_findings,
        "threat_actor_profile": {
            "likely_motivation": "Unknown — insufficient data for automated attribution.",
            "operational_security": "Indeterminate from available data.",
            "estimated_sophistication": "Unknown",
            "indicators_of_attribution": [f["feature_value"] for f in high_conf[:5]],
        },
        "ioc_analysis": {
            "high_value": [f["feature_value"] for f in high_conf[:10]],
            "notes": f"Auto-generated from {len(high_conf)} high-confidence (≥0.85) indicators.",
        },
        "attack_vectors": ["Dark web forum/marketplace activity detected."],
        "recommendations": [
            "Cross-reference extracted usernames against known threat actor databases.",
            "Block identified crypto wallets on exchange watch-lists.",
            "Report email addresses to threat intelligence sharing platforms (ISACs).",
            "Escalate to senior analyst for manual review.",
        ],
        "investigative_leads": (
            [f"Pivot on {f['feature_type']}: {f['feature_value']}" for f in high_conf[:5]]
            or ["No high-confidence leads automatically identified."]
        ),
    }


# ---------------------------------------------------------------------------
# LLM-backed report builder
# ---------------------------------------------------------------------------
def _auto_generate_report_data(
    domain_id: str,
    page_id: str,
    page_text: str,
    features: List[Dict],
) -> Dict:
    """Ask Gemini for a structured report. Falls back to computed report on failure."""
    by_type = Counter(f.get("feature_type", "other") for f in features)
    high_conf = [f for f in features if (f.get("confidence_score") or 0) >= 0.9]

    feature_summary = "\n".join(
        f"  [{k.upper()}] {v} found" for k, v in by_type.items()
    ) or "  (none)"

    hc_summary = "\n".join(
        f"  - [{f['feature_type']}] {f['feature_value']}" for f in high_conf[:10]
    ) or "  (none)"

    prompt_text = f"""INVESTIGATION TARGET:
  Domain ID: {domain_id}
  Page ID:   {page_id}
  Document size: {len(page_text)} characters

EXTRACTED INDICATORS:
{feature_summary}

HIGH-CONFIDENCE INDICATORS (≥0.90):
{hc_summary}

DOCUMENT EXCERPT (first 2500 chars):
{page_text[:2500]}

Write a formal CTI investigation report as JSON matching this schema:
{REPORT_SCHEMA_DESCRIPTION}
"""

    llm = get_gemini_llm(temperature=0.2, max_tokens=2048)
    if not llm:
        print("[Report] GOOGLE_API_KEY not set — using fallback report.")
        return _fallback_report(features, page_text)

    try:
        response = llm.invoke([
            SystemMessage(content=REPORT_SYSTEM_PROMPT),
            HumanMessage(content=prompt_text),
        ])
        text = getattr(response, "content", "") or ""
        parsed = parse_json_object(text)

        if parsed:
            print(f"[Report] Parsed JSON via gemini:{DEFAULT_GEMINI_MODEL}")
            return parsed

        print("[Report] Gemini returned non-JSON; using fallback report.")
        return _fallback_report(features, page_text)

    except Exception as e:
        print(f"[Report] Gemini failed: {type(e).__name__}: {str(e)[:200]}")
        return _fallback_report(features, page_text)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def generate_investigation_report(
    domain_id: str,
    page_id: str,
    page_url: str,
    page_name: str,
    page_text: str,
    features: List[Dict],
) -> Dict:
    """
    Full report generation pipeline.
    Returns a complete structured report dict ready for frontend rendering.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    by_type = Counter(f.get("feature_type", "other") for f in features)

    llm_data = _auto_generate_report_data(domain_id, page_id, page_text, features)

    return {
        "metadata": {
            "report_id": f"GDK-{now.strftime('%Y%m%d-%H%M%S')}",
            "generated_at": now.isoformat(),
            "classification": "TLP:AMBER — For authorized analyst use only",
            "analyst_system": "GUDAKESA AI CTI Platform v1.0",
            "domain_id": domain_id,
            "page_id": page_id,
            "page_url": page_url,
            "page_name": page_name,
            "document_size_chars": len(page_text),
            "total_indicators": len(features),
        },
        "statistics": {
            "by_type": dict(by_type),
            "high_confidence_count": sum(
                1 for f in features if (f.get("confidence_score") or 0) >= 0.85
            ),
            "avg_confidence": round(
                sum(f.get("confidence_score") or 0.7 for f in features)
                / max(len(features), 1),
                3,
            ),
        },
        "indicators": features,
        "analysis": llm_data,
    }