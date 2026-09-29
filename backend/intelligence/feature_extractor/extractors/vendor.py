"""
extractor/extractors/vendor.py
Extracts vendor/seller profiles, ratings, shop names, and contact/security intelligence.
"""
import re
from typing import Any, Dict, List, Optional
from .. import patterns
from .base import make_provenance
from ..loader import TextLoader


def _clean_vendor_name(name: str) -> str:
    """Clean vendor name from markdown and artifacts."""
    if not name:
        return ""
    name = re.sub(r"\s+Skip to.*", "", name, flags=re.I)
    name = re.sub(r"\s+Check link.*", "", name, flags=re.I)
    name = re.sub(r"\s+Page \d+.*", "", name, flags=re.I)
    name = name.strip().strip("*").strip()
    return name


def extract_vendor(loader: TextLoader) -> Optional[Dict[str, Any]]:
    """Extract vendor profile from product or shop page."""
    text = loader.raw_text

    vendor_name = None
    vendor_line = None
    vendor_rating = None
    vendor_type = "marketplace_vendor"

    # 1. Check Multiline Vendor Block
    vm = patterns.VENDOR_MULTILINE.search(text)
    if vm:
        cand = _clean_vendor_name(vm.group(1))
        if cand and cand.lower() not in ["description", "reviews", "inquiries", "more offers", "store policies"]:
            vendor_name = cand
            vendor_line = loader.char_offset_to_line(vm.start())
            if vm.group(2):
                try:
                    vendor_rating = float(vm.group(2))
                except ValueError:
                    pass

    # 2. Check Inline Vendor Label
    if not vendor_name:
        vi = patterns.VENDOR_INLINE.search(text)
        if vi:
            cand = _clean_vendor_name(vi.group(1))
            if cand and cand.lower() not in ["description", "reviews", "inquiries", "cart"]:
                vendor_name = cand
                vendor_line = loader.char_offset_to_line(vi.start())

    # 3. Check Copyright Brand
    if not vendor_name:
        cp_m = patterns.COPYRIGHT_VENDOR.search(text)
        if cp_m:
            vendor_name = _clean_vendor_name(cp_m.group(1))
            vendor_line = loader.char_offset_to_line(cp_m.start())
            vendor_type = "site_operator"

    # 4. Check Welcome Header
    if not vendor_name:
        wc_m = patterns.WELCOME_HEADER.search(text)
        if wc_m:
            vendor_name = _clean_vendor_name(wc_m.group(1))
            vendor_line = loader.char_offset_to_line(wc_m.start())
            vendor_type = "site_operator"

    # 5. Check Title Suffix
    if not vendor_name and loader.lines:
        ts_m = patterns.SITE_TITLE_SUFFIX.search(loader.lines[0])
        if ts_m:
            cand = _clean_vendor_name(ts_m.group(1))
            if cand.lower() not in ["home", "shop", "checkout", "cart", "navigation"]:
                vendor_name = cand
                vendor_line = 1
                vendor_type = "site_operator"

    if not vendor_name:
        return None

    if not vendor_rating and vendor_line and vendor_type == "marketplace_vendor":
        nearby = "\n".join(loader.get_lines(vendor_line, vendor_line + 4))
        r_match = patterns.VENDOR_RATING.search(nearby)
        if r_match:
            try:
                vendor_rating = float(r_match.group(1))
            except ValueError:
                pass

    contacts = {}
    tg_m = patterns.TELEGRAM_HANDLE.search(text)
    if tg_m and tg_m.group(1).lower() not in ["proton", "gmail", "yahoo", "content", "cart"]:
        contacts["telegram"] = tg_m.group(1)
    email_m = patterns.EMAIL_ADDR.search(text)
    if email_m:
        contacts["email"] = email_m.group(1)
    jabber_m = patterns.JABBER_XMPP.search(text)
    if jabber_m:
        contacts["jabber"] = jabber_m.group(1)

    crypto_accepted = []
    if patterns.PRICE_BTC.search(text) or "bitcoin" in text.lower() or "btc" in text.lower():
        crypto_accepted.append("Bitcoin (BTC)")
    if patterns.PRICE_XMR.search(text) or "monero" in text.lower() or "xmr" in text.lower():
        crypto_accepted.append("Monero (XMR)")
    if "cryptocurrency" in text.lower() and not crypto_accepted:
        crypto_accepted.append("Cryptocurrency (General)")

    return {
        "name": vendor_name,
        "type": vendor_type,
        "rating": vendor_rating,
        "contacts": contacts if contacts else None,
        "crypto_accepted": crypto_accepted if crypto_accepted else None,
        "provenance": make_provenance(
            loader.filename,
            line_start=vendor_line,
            method="regex_vendor",
        ),
    }


def extract_top_vendors_sidebar(loader: TextLoader) -> List[Dict[str, Any]]:
    """Extract top rated vendors listed in sidebars."""
    text = loader.raw_text
    vendors = []

    header_m = patterns.TOP_RATED_VENDORS_HEADER.search(text)
    if not header_m:
        return vendors

    start_pos = header_m.end()
    next_sec = patterns.H2_SECTION.search(text[start_pos:])
    section_text = text[start_pos:start_pos + next_sec.start()] if next_sec else text[start_pos:]

    lines = section_text.strip().split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("* ") or line.startswith("- "):
            name = line.lstrip("*- ").strip()
            rating = None
            for j in range(i + 1, min(i + 4, len(lines))):
                rm = patterns.VENDOR_RATING.search(lines[j])
                if rm:
                    try:
                        rating = float(rm.group(1))
                    except ValueError:
                        pass
                    break
            if name:
                vendors.append({"name": name, "rating": rating})
        i += 1

    return vendors
