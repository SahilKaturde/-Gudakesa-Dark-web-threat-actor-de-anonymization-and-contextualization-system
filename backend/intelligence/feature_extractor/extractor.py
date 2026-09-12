"""
Feature extractor for GUDAKESA Intelligence Feature Extractor.
Gemini + hardened regex + validation pipeline.

Tiers:
  1. Gemini (structured output, few-shot)
  2. Regex (validated, deduped, false-positive filtered)

Entity types emitted:
  Syntactic (regex-capable): email, ip, crypto_wallet, pgp_key, onion_url,
                              username, xmpp
  Semantic  (Gemini only)  : product, post, review, other
"""
import re
from typing import List, Dict, Set, Tuple, Iterable

from langchain_core.prompts import ChatPromptTemplate

from .llm import get_gemini_llm, DEFAULT_GEMINI_MODEL
from .schemas import ExtractedFeatureBatch, ExtractedEntityItem


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GEMINI_DOC_CHARS = 24000


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
# NOTE ON ORDER: more specific patterns must come before looser ones when
# they overlap (e.g. onion-email before generic email; armored PGP block
# before bare fingerprint).
REGEX_PATTERNS: List[Tuple[str, str, float]] = [

    # --- Emails -----------------------------------------------------------
    # .onion-email first so it wins over the generic TLD rule
    ("email", r'[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9\-]{1,255}\.onion\b', 0.98),
    ("email", r'(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]{1,64}@'
              r'(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.){1,4}'
              r'[A-Za-z]{2,24}(?![A-Za-z0-9\-])', 0.95),

    # --- Onion URLs -------------------------------------------------------
    ("onion_url", r'\bhttps?://[a-z2-7]{16,56}\.onion(?:[/A-Za-z0-9\-\.\?=&%#_~]*)?', 0.99),
    ("onion_url", r'\b[a-z2-7]{56}\.onion\b', 0.97),
    ("onion_url", r'\b[a-z2-7]{16}\.onion\b', 0.92),

    # --- IPv4 (each octet 0-255) ------------------------------------------
    ("ip", r'\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}'
           r'(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b', 0.92),

    # --- Crypto wallets ---------------------------------------------------
    # Bitcoin bech32 (bc1q…42 chars, bc1p…62 chars)
    ("crypto_wallet", r'\bbc1[ac-hj-np-z02-9]{11,71}\b', 0.98),
    # Bitcoin legacy / P2SH
    ("crypto_wallet", r'\b[13][1-9A-HJ-NP-Za-km-z]{25,34}\b', 0.97),
    # Ethereum
    ("crypto_wallet", r'\b0x[a-fA-F0-9]{40}\b', 0.98),
    # Monero standard (95 chars, starts '4') and subaddress (starts '8')
    ("crypto_wallet", r'\b[48][0-9AB][1-9A-HJ-NP-Za-km-z]{93}\b', 0.98),
    # Litecoin bech32 + legacy
    ("crypto_wallet", r'\bltc1[ac-hj-np-z02-9]{11,71}\b', 0.98),
    ("crypto_wallet", r'\b[LM][1-9A-HJ-NP-Za-km-z]{26,33}\b', 0.95),
    # Dogecoin
    ("crypto_wallet", r'\bD[5-9A-HJ-NP-U][1-9A-HJ-NP-Za-km-z]{32}\b', 0.95),
    # Zcash transparent (t1… / t3…)
    ("crypto_wallet", r'\bt[13][1-9A-HJ-NP-Za-km-z]{33}\b', 0.90),
    # TRON
    ("crypto_wallet", r'\bT[1-9A-HJ-NP-Za-km-z]{33}\b', 0.90),

    # --- PGP --------------------------------------------------------------
    # Full armored public key block — highest-confidence signal there is
    ("pgp_key", r'-----BEGIN PGP PUBLIC KEY BLOCK-----'
                r'[\s\S]{50,}?'
                r'-----END PGP PUBLIC KEY BLOCK-----', 0.99),
    # Fingerprint, only when explicitly labeled
    ("pgp_key", r'(?:fingerprint|fpr|key[\s\-]?id)[\s:=\-]*'
                r'((?:[0-9A-Fa-f]{4}[\s:]*){9,15}[0-9A-Fa-f]{4})', 0.90),

    # --- Usernames --------------------------------------------------------
    # Profile-style URL paths
    ("username", r'/(?:user|users|profile|profiles|vendor|vendors|member|members|u)/'
                 r'([A-Za-z0-9_\-\.]{3,32})(?![A-Za-z0-9_\-\.])', 0.90),
    # Messaging-app usernames (Telegram, Wickr, Session, Signal, Threema)
    ("username",
     r'(?:telegram|tg|wickr|wickrme|session|signal|threema|tox)'
     r'[\s:_\-]*(?:id|user|handle)?[\s:_\-]*'
     r'@?([A-Za-z][A-Za-z0-9_\.\-]{3,31})(?![A-Za-z0-9_\-\.])', 0.90),
    # Generic @-handle — guarded against emails by lookbehind + post-filter
    ("username", r'(?<![A-Za-z0-9._%+\-])@([A-Za-z][A-Za-z0-9_]{3,31})\b', 0.82),

    # --- XMPP / Jabber ----------------------------------------------------
    ("xmpp", r'\b[A-Za-z0-9._%+\-]{1,64}@'
             r'(?:jabber\.[A-Za-z]{2,}|xmpp\.[A-Za-z]{2,}|'
             r'[A-Za-z0-9\-]+\.(?:im|chat|jabber|onion))\b', 0.90),
]


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
_IP_OCTET_RE = re.compile(r'^\d{1,3}(\.\d{1,3}){3}$')
_HEX_RE = re.compile(r'^[0-9A-Fa-f]+$')

# Common domain suffixes that look like @-handles when someone writes "foo@gmail"
_HANDLE_BLACKLIST: Set[str] = {
    "gmail", "yahoo", "outlook", "hotmail", "protonmail", "proton",
    "aol", "icloud", "mail", "yandex", "zoho", "gmx", "tutanota",
    "tuta", "fastmail", "hushmail", "riseup", "onionmail", "mail2tor",
}


def _is_valid_ip(v: str) -> bool:
    if not _IP_OCTET_RE.match(v):
        return False
    try:
        return all(0 <= int(p) <= 255 for p in v.split("."))
    except ValueError:
        return False


def _is_valid_pgp_fingerprint(v: str) -> bool:
    """40-char (v4) or 64-char (v5) hex, ignoring whitespace/colons."""
    compact = re.sub(r'[\s:]', '', v)
    return len(compact) in (40, 64) and bool(_HEX_RE.match(compact))


def _is_blacklisted_handle(v: str) -> bool:
    return v.lower() in _HANDLE_BLACKLIST


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------
def _normalize(feature_type: str, value: str) -> str:
    """Canonicalize a value by type. Returns '' if it should be dropped."""
    v = value.strip().strip('.,;:"\')')
    if not v:
        return ""

    if feature_type in ("email", "xmpp", "username", "onion_url"):
        # Preserve original case for usernames (handles are case-sensitive in some apps)
        if feature_type == "username":
            return v
        return v.lower()

    if feature_type == "ip":
        return v  # digits + dots only

    if feature_type == "crypto_wallet":
        # Wallet case matters for base58 (BTC/XMR/etc.), lowercase for bech32/hex
        if v.startswith(("bc1", "ltc1", "0x")):
            return v.lower()
        return v

    if feature_type == "pgp_key":
        # For armored blocks keep as-is; for fingerprints compact whitespace
        if v.startswith("-----BEGIN"):
            return v
        return re.sub(r'[\s:]', '', v).upper()

    return v


def _validate(feature_type: str, value: str) -> bool:
    """Final gate — reject anything that fails type-specific validation."""
    if not value:
        return False

    if feature_type == "ip":
        return _is_valid_ip(value)

    if feature_type == "pgp_key" and not value.startswith("-----BEGIN"):
        return _is_valid_pgp_fingerprint(value)

    if feature_type == "username":
        if _is_blacklisted_handle(value):
            return False
        # Reject pure-hex 32+ char strings (likely txids / hashes)
        if len(value) >= 32 and _HEX_RE.match(value):
            return False

    if feature_type == "crypto_wallet":
        # Reject obvious non-addresses
        if len(value) < 26:
            return False

    return True


def _strip_emails_from(text: str, emails: Iterable[str]) -> str:
    """Blank out detected emails so generic @-handle patterns don't re-match."""
    out = text
    for e in emails:
        if e:
            out = out.replace(e, " " * len(e))
    return out


def _dedupe(items: List[ExtractedEntityItem]) -> List[ExtractedEntityItem]:
    """
    Case-insensitive dedupe, keeping the highest-confidence variant.
    Preserves first-seen order otherwise.
    """
    best: Dict[Tuple[str, str], ExtractedEntityItem] = {}
    order: List[Tuple[str, str]] = []

    for it in items:
        key = (it.feature_type.lower(), it.feature_value.lower())
        if key not in best:
            best[key] = it
            order.append(key)
        else:
            if (it.confidence_score or 0) > (best[key].confidence_score or 0):
                best[key] = it

    return [best[k] for k in order]


# ---------------------------------------------------------------------------
# Regex extractor
# ---------------------------------------------------------------------------
def regex_fallback_extractor(text: str) -> List[ExtractedEntityItem]:
    """
    Rule-based extraction with validation and de-duplication.
    Strong enough to be the guaranteed tier — but no semantic extraction.
    """
    if not text:
        return []

    raw: List[ExtractedEntityItem] = []
    seen_values_by_type: Dict[str, Set[str]] = {}

    # Pre-pass: collect emails so we can blank them before @-handle scanning
    email_pat = re.compile(REGEX_PATTERNS[1][1])
    detected_emails = [m.group(0) for m in email_pat.finditer(text)]
    scrubbed = _strip_emails_from(text, detected_emails)

    for f_type, pattern, base_score in REGEX_PATTERNS:
        try:
            target = scrubbed if f_type in ("username",) else text
            for match in re.finditer(pattern, target):
                val = match.group(1) if match.groups() else match.group(0)
                val = _normalize(f_type, val)
                if not _validate(f_type, val):
                    continue

                type_seen = seen_values_by_type.setdefault(f_type, set())
                if val.lower() in type_seen:
                    continue
                type_seen.add(val.lower())

                start = max(0, match.start() - 40)
                end = min(len(text), match.end() + 40)
                snippet = text[start:end].replace('\n', ' ').strip()

                raw.append(ExtractedEntityItem(
                    feature_type=f_type,
                    feature_value=val,
                    context=snippet[:250],
                    description=f"Rule-based regex detected {f_type}",
                    confidence_score=base_score,
                ))
        except Exception as e:
            print(f"[Regex Warning] {f_type} pattern error: {e}")

    return _dedupe(raw)


# ---------------------------------------------------------------------------
# Gemini extraction
# ---------------------------------------------------------------------------
EXTRACT_SYSTEM_PROMPT = """You are an elite Cyber Threat Intelligence (CTI) extraction agent.
You extract structured entities from scraped dark-web text (forums, markets, leak sites).

━━━ ENTITY TYPES ━━━
Syntactic (find every literal occurrence):
  email         — full email address
  username      — handle, alias, vendor name, or forum account
  ip            — IPv4 address
  crypto_wallet — any cryptocurrency address (BTC, ETH, XMR, LTC, DOGE, ZEC, TRON)
  pgp_key       — armored PGP public key block OR a labeled fingerprint
  onion_url     — v2/v3 .onion URL or bare host
  xmpp          — Jabber/XMPP address

Semantic (infer from context):
  product       — item being sold (name, strain, drug, service)
  post          — forum thread or listing title
  review        — buyer feedback / vendor rating text
  other         — anything valuable that fits none of the above

━━━ OUTPUT FIELDS ━━━
  feature_type     — one of the types above (lowercase)
  feature_value    — the EXACT string as it appears (do not paraphrase)
  context          — 1-2 sentence excerpt that PROVES the extraction
  description      — short label ("Vendor Telegram handle", "BTC wallet for escrow")
  confidence_score — 0.0 – 1.0 (see rubric)

━━━ CONFIDENCE RUBRIC ━━━
  0.95–1.00  Exact-format match with unambiguous context
             (wallet passes format check, armored PGP block, complete email)
  0.80–0.94  Clear context but minor ambiguity
             (handle mentioned as alias but not explicitly "contact @x")
  0.60–0.79  Plausible but context is weak or the value could be something else
  below 0.60 DO NOT INCLUDE — return nothing for this candidate

━━━ RULES ━━━
1. Extract EVERY distinct occurrence. Do not deduplicate within your output.
2. NEVER invent values. If it's not literally in the text, don't return it.
3. NEVER paraphrase a value. `feature_value` must be a verbatim substring.
4. Do NOT return usernames that are parts of email addresses.
5. Do NOT return a wallet address unless it matches the format of that chain.
6. Do NOT return common English words as usernames.
7. `context` MUST be a real substring of the source text (you may trim with "…").
8. If nothing extractable is present, return an empty features list.

━━━ EXAMPLES ━━━

INPUT: "Contact vendor @dark_market_01 or email darkmarket@protonmail.com for bulk orders. BTC: bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"
OUTPUT:
[
  {"feature_type":"username","feature_value":"dark_market_01",
   "context":"Contact vendor @dark_market_01 or email darkmarket@protonmail.com",
   "description":"Vendor Telegram handle","confidence_score":0.92},
  {"feature_type":"email","feature_value":"darkmarket@protonmail.com",
   "context":"or email darkmarket@protonmail.com for bulk orders",
   "description":"Vendor contact email","confidence_score":0.95},
  {"feature_type":"crypto_wallet","feature_value":"bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
   "context":"BTC: bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
   "description":"Bitcoin wallet for payments","confidence_score":0.98}
]

INPUT: "Seller claims 5g of Afghan heroin at $120 per gram. Buyer @user_xyz gave 5 stars."
OUTPUT:
[
  {"feature_type":"product","feature_value":"Afghan heroin",
   "context":"5g of Afghan heroin at $120 per gram",
   "description":"Listed narcotic product","confidence_score":0.90},
  {"feature_type":"username","feature_value":"user_xyz",
   "context":"Buyer @user_xyz gave 5 stars",
   "description":"Forum buyer handle","confidence_score":0.85},
  {"feature_type":"review","feature_value":"gave 5 stars",
   "context":"Buyer @user_xyz gave 5 stars",
   "description":"Buyer feedback","confidence_score":0.80}
]

NEGATIVE — do NOT extract:
  • "@gmail" from "user@gmail.com" (that's part of an email, not a handle)
  • "admin", "user", "test" as usernames (too generic)
  • Any address that fails the chain's format (e.g. a 20-char string as a BTC address)
"""

EXTRACT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", EXTRACT_SYSTEM_PROMPT),
    ("human", "Scraped Dark Web Document Text:\n\n{text}"),
])


def _try_gemini(text: str) -> List[ExtractedEntityItem]:
    """Run Gemini structured extraction. Returns [] on any failure."""
    llm = get_gemini_llm(temperature=0.1, max_tokens=8000)
    if not llm:
        print("[AI Extractor] GOOGLE_API_KEY not set — skipping Gemini")
        return []

    try:
        structured_llm = llm.with_structured_output(ExtractedFeatureBatch)
        chain = EXTRACT_PROMPT | structured_llm

        result: ExtractedFeatureBatch = chain.invoke(
            {"text": text[:GEMINI_DOC_CHARS]}
        )

        features = result.features if result and result.features else []
        if not features:
            print("[AI Extractor] Gemini returned 0 features.")
            return []

        # Pass Gemini output through the same validation/dedup pipeline
        cleaned: List[ExtractedEntityItem] = []
        for f in features:
            v = _normalize(f.feature_type, f.feature_value)
            if not _validate(f.feature_type, v):
                continue
            cleaned.append(ExtractedEntityItem(
                feature_type=f.feature_type,
                feature_value=v,
                context=(f.context or "")[:250],
                description=(f.description or "")[:250],
                confidence_score=f.confidence_score,
            ))

        cleaned = _dedupe(cleaned)
        print(f"[AI Extractor] Gemini ({DEFAULT_GEMINI_MODEL}) "
              f"extracted {len(features)} raw → {len(cleaned)} validated features.")
        return cleaned

    except Exception as e:
        print(f"[AI Extractor] Gemini failed: {type(e).__name__}: {str(e)[:240]}")
        return []


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def extract_features_with_llm(text: str) -> List[ExtractedEntityItem]:
    """
    Extract entities from scraped text.

    Strategy:
      1. Run both Gemini AND regex.
      2. Union the results, deduping by (type, value) — regex fills syntactic
         gaps Gemini missed; Gemini contributes semantic types regex can't.
      3. If Gemini yields nothing, regex alone is the answer.
    """
    if not text or not text.strip():
        return []

    gemini_features = _try_gemini(text)
    regex_features = regex_fallback_extractor(text)

    if gemini_features and regex_features:
        # Regex wins ties on syntactic types (deterministic); Gemini wins on semantic.
        combined = gemini_features + regex_features
        merged = _dedupe(combined)
        print(f"[AI Extractor] Merged: {len(gemini_features)} gemini + "
              f"{len(regex_features)} regex → {len(merged)} unique.")
        return merged

    if gemini_features:
        return gemini_features
    if regex_features:
        print("[AI Extractor] Gemini returned nothing — using regex only.")
        return regex_features

    print("[AI Extractor] No features extracted.")
    return []