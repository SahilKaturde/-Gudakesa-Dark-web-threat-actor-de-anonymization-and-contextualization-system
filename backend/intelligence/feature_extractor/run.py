"""
extractor/run.py
CLI command-line interface for the Darkweb Feature Extractor.
Processes scraped .onion data folders, applies hybrid regex + LLM extraction,
and generates law-enforcement intelligence reports.
"""
import argparse
import json
import logging
import pathlib
import sys
import time
from typing import Any, Dict, List

# Add workspace to path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from extractor.config import MIN_FEATURES_REGEX
from extractor.loader import TextLoader
from extractor.classifier import classify_page, PageType
from extractor.extractors.product import extract_product
from extractor.extractors.review import extract_reviews
from extractor.extractors.vendor import extract_vendor, extract_top_vendors_sidebar
from extractor.extractors.catalog import extract_catalog
from extractor.extractors.sidebar import extract_sidebar
from extractor.llm.client import is_ollama_available
from extractor.llm.fallback_extractor import llm_fallback_extract
from extractor.summarizer import summarize_page
from extractor.aggregator import aggregate_all
from extractor.report import save_json_report, save_markdown_report

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
log = logging.getLogger("darkweb-intel")

BANNER = """\033[1;36m
╔══════════════════════════════════════════════════════╗
║     Darkweb Feature Extractor v1.1                  ║
║     Hybrid Regex + LLM (qwen3:1.7b) Pipeline       ║
╚══════════════════════════════════════════════════════╝\033[0m"""


def count_features(features: Dict[str, Any]) -> int:
    """Count extracted features to assess confidence."""
    count = 0
    product = features.get("product")
    if product and isinstance(product, dict):
        if product.get("title"):
            count += 1
        if product.get("prices"):
            count += 1
        if product.get("category") or product.get("category_path"):
            count += 1
        if product.get("specs"):
            count += 1
        if product.get("tags"):
            count += 1

    vendor = features.get("vendor")
    if vendor and isinstance(vendor, dict) and vendor.get("name"):
        count += 1

    count += len(features.get("reviews") or [])
    count += len(features.get("catalog_products") or [])
    return count


def process_file(loader: TextLoader, ollama_ok: bool) -> Dict[str, Any]:
    """Run single page extraction pipeline."""
    text = loader.raw_text

    page_type = classify_page(text)

    features: Dict[str, Any] = {
        "file": loader.filename,
        "page_type": page_type,
    }

    if page_type == PageType.PRODUCT_DETAIL:
        features["product"] = extract_product(loader)
        features["reviews"] = extract_reviews(loader)
        features["vendor"] = extract_vendor(loader)
        features["catalog_products"] = []
    elif page_type == PageType.CATALOG_LISTING:
        features["product"] = None
        features["reviews"] = []
        features["vendor"] = extract_vendor(loader)
        features["catalog_products"] = extract_catalog(loader)
    else:
        features["product"] = extract_product(loader)
        features["reviews"] = extract_reviews(loader)
        features["vendor"] = extract_vendor(loader)
        features["catalog_products"] = []

    features["sidebar"] = extract_sidebar(loader)
    top_v = extract_top_vendors_sidebar(loader)
    if top_v:
        features["sidebar"]["top_vendors"] = top_v

    feat_count = count_features(features)
    features["feature_count"] = feat_count

    if feat_count < MIN_FEATURES_REGEX and ollama_ok:
        llm_data = llm_fallback_extract(loader)
        if not features.get("product") and llm_data.get("product"):
            features["product"] = llm_data["product"]
            features["product_source"] = "llm"
        if not features.get("reviews") and llm_data.get("reviews"):
            features["reviews"] = llm_data["reviews"]
        if not features.get("vendor") and llm_data.get("vendor"):
            features["vendor"] = llm_data["vendor"]

    features["summary"] = summarize_page(loader, features)

    return features


def main():
    parser = argparse.ArgumentParser(
        description="Darkweb Feature Extractor - Structured Intelligence from Scraped Pages."
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Path to folder containing .txt files or single .txt file.",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory for features.json and intel_report.md (default: <parent>/extracted)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM fallback and enforce fast deterministic regex mode.",
    )

    args = parser.parse_args()

    print(BANNER)

    target_path_str = args.target
    if not target_path_str:
        raw = input("Enter path to folder or file containing scraped .txt files:\n> ").strip()
        target_path_str = raw

    target_path = pathlib.Path(target_path_str)
    if not target_path.exists():
        print(f"\033[91mError: '{target_path}' does not exist.\033[0m")
        sys.exit(1)

    if target_path.is_file():
        txt_files = [target_path]
        source_folder = str(target_path.parent)
        default_out = target_path.parent / "extracted"
    else:
        txt_files = sorted(target_path.glob("page_*.txt"))
        if not txt_files:
            txt_files = sorted(target_path.glob("*.txt"))
        source_folder = str(target_path)
        default_out = target_path.parent / "extracted"

    if not txt_files:
        print(f"\033[91mNo .txt files found in '{target_path}'.\033[0m")
        sys.exit(1)

    output_dir = pathlib.Path(args.output) if args.output else default_out
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\033[1m[INFO]\033[0m Found {len(txt_files)} file(s) to process")

    ollama_ok = False if args.no_llm else is_ollama_available()
    if ollama_ok:
        print("\033[1;32m[INFO]\033[0m Ollama + qwen3:1.7b is active (LLM synthesis enabled)")
    else:
        mode_msg = "Regex mode forced (--no-llm)" if args.no_llm else "Ollama offline — running fast regex + template synthesis mode"
        print(f"\033[1;33m[WARN]\033[0m {mode_msg}")

    all_pages: List[Dict[str, Any]] = []
    start_time = time.time()
    type_counts = {"PRODUCT_DETAIL": 0, "CATALOG_LISTING": 0, "GENERAL": 0}

    for i, txt_file in enumerate(txt_files, 1):
        loader = TextLoader(txt_file)
        feat = process_file(loader, ollama_ok)
        all_pages.append(feat)

        ptype = feat.get("page_type", "GENERAL")
        type_counts[ptype] = type_counts.get(ptype, 0) + 1

        icon = {"PRODUCT_DETAIL": "📦", "CATALOG_LISTING": "📋", "GENERAL": "📄"}.get(ptype, "📄")
        fcount = feat.get("feature_count", 0)
        rcnt = len(feat.get("reviews") or [])
        r_str = f" | {rcnt} review(s)" if rcnt else ""
        print(f"  {icon} [{i:02d}/{len(txt_files):02d}] {txt_file.name} → {ptype:16s} ({fcount} features{r_str})")

    elapsed = time.time() - start_time

    print(f"\n\033[1m[INFO]\033[0m Page Classification Breakdown:")
    for pt, cnt in type_counts.items():
        print(f"  → {pt:16s}: {cnt}")

    print("\n\033[1m[INFO]\033[0m Generating cross-page intelligence synthesis with deduplication...")
    aggregation = aggregate_all(all_pages)

    vendors = aggregation.get("vendor_dossiers", {})
    users = aggregation.get("user_profiles", {})
    total_revs = sum(len(p.get("reviews") or []) for p in all_pages)

    print(f"  → {len(vendors)} distinct vendor dossier(s) compiled")
    print(f"  → {len(users)} unique user profile(s) compiled ({total_revs} total customer reviews)")

    json_file = save_json_report(all_pages, aggregation, output_dir, source_folder)
    md_file = save_markdown_report(all_pages, aggregation, output_dir, source_folder)

    print(f"\n\033[1;32m✅ Pipeline completed successfully in {elapsed:.2f}s\033[0m")
    print(f"  📁 Structured JSON Deliverable : {json_file}")
    print(f"  📄 Investigation MD Brief     : {md_file}")


if __name__ == "__main__":
    main()
