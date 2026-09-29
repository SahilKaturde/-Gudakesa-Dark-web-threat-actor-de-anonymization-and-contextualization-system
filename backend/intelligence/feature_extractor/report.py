"""
extractor/report.py
Generates structured intelligence deliverables:
1. features.json - Machine-readable extraction data with provenance
2. intel_report.md - Executive law enforcement investigation dossier
"""
import json
import datetime
import pathlib
from typing import Any, Dict, List


def save_json_report(
    pages: List[Dict[str, Any]],
    aggregation: Dict[str, Any],
    output_dir: pathlib.Path,
    source_folder: str,
) -> pathlib.Path:
    """Export comprehensive JSON intelligence deliverable."""
    report = {
        "metadata": {
            "source_folder": str(source_folder),
            "total_files_processed": len(pages),
            "extraction_timestamp": datetime.datetime.now().isoformat(),
            "pipeline_version": "1.1.0",
        },
        "investigation_summary": {
            "product_detail_pages": sum(1 for p in pages if p.get("page_type") == "PRODUCT_DETAIL"),
            "catalog_listing_pages": sum(1 for p in pages if p.get("page_type") == "CATALOG_LISTING"),
            "general_pages": sum(1 for p in pages if p.get("page_type") == "GENERAL"),
            "total_unique_vendors": len(aggregation.get("vendor_dossiers", {})),
            "total_unique_reviewers": len(aggregation.get("user_profiles", {})),
            "total_reviews_extracted": sum(len(p.get("reviews") or []) for p in pages),
        },
        "vendor_dossiers": aggregation.get("vendor_dossiers", {}),
        "user_profiles": aggregation.get("user_profiles", {}),
        "pages": pages,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "features.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    return out_path


def save_markdown_report(
    pages: List[Dict[str, Any]],
    aggregation: Dict[str, Any],
    output_dir: pathlib.Path,
    source_folder: str,
) -> pathlib.Path:
    """Export executive markdown intelligence brief."""
    lines = []
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    product_pages = [p for p in pages if p.get("page_type") == "PRODUCT_DETAIL"]
    catalog_pages = [p for p in pages if p.get("page_type") == "CATALOG_LISTING"]
    general_pages = [p for p in pages if p.get("page_type") == "GENERAL"]

    vendors = aggregation.get("vendor_dossiers", {})
    users = aggregation.get("user_profiles", {})
    total_reviews = sum(len(p.get("reviews") or []) for p in pages)

    lines.append("# 🕵️ DARKWEB INTELLIGENCE REPORT")
    lines.append(f"**Target Directory:** `{source_folder}`  ")
    lines.append(f"**Generated:** {now}  ")
    lines.append(f"**Classification:** LAW ENFORCEMENT SENSITIVE  ")
    lines.append("")

    # 1. Executive Summary
    lines.append("## 1. Executive Summary")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| **Scraped Files Processed** | `{len(pages)}` |")
    lines.append(f"| **Product Detail Pages** | `{len(product_pages)}` |")
    lines.append(f"| **Catalog / Listing Pages** | `{len(catalog_pages)}` |")
    lines.append(f"| **General / Policy / FAQ Pages** | `{len(general_pages)}` |")
    lines.append(f"| **Distinct Vendors Identified** | `{len(vendors)}` |")
    lines.append(f"| **Customer Reviews Extracted** | `{total_reviews}` |")
    lines.append(f"| **Unique Reviewers Profiled** | `{len(users)}` |")
    lines.append("")

    # 2. Vendor Dossiers (Deduplicated)
    lines.append("## 2. Vendor & Marketplace Dossiers")
    if vendors:
        for name, vdata in sorted(vendors.items(), key=lambda x: x[1].get("product_count", 0), reverse=True):
            v_type = vdata.get("vendor_type", "vendor").replace("_", " ").title()
            rating_str = f" ⭐ {vdata['rating']}/5" if vdata.get("rating") else ""
            lines.append(f"### 🏷️ {name} ({v_type}){rating_str}")
            lines.append(f"- **Distinct Products Identified:** {vdata.get('product_count', 0)}")
            if vdata.get("categories"):
                lines.append(f"- **Categories:** {', '.join(vdata['categories'])}")
            if vdata.get("crypto_accepted"):
                lines.append(f"- **Payment / Crypto Accepted:** {', '.join(vdata['crypto_accepted'])}")
            if vdata.get("contacts"):
                contacts_str = ", ".join(f"{k}: `{v}`" for k, v in vdata["contacts"].items())
                lines.append(f"- **Contact Handles:** {contacts_str}")
            lines.append(f"- **Observed across {len(vdata.get('pages_found_on', []))} page(s):** `{', '.join(vdata.get('pages_found_on', [])[:8])}`")
            lines.append("")

            prods = vdata.get("unique_products", [])
            if prods:
                lines.append("| Product Name | Price | Occurrences | Seen In Pages |")
                lines.append("|---|---|---|---|")
                for p in prods[:20]:
                    seen_str = ", ".join(p.get("found_in_pages", [])[:3])
                    lines.append(f"| {p.get('title', 'N/A')} | {p.get('price', 'N/A')} | {p.get('occurrence_count', 1)} | `{seen_str}` |")
                lines.append("")
    else:
        lines.append("_No explicit vendor labels found._\n")

    # 3. User / Reviewer Profiles
    lines.append("## 3. User & Reviewer Profiles")
    if users:
        sorted_users = sorted(users.items(), key=lambda x: x[1].get("total_reviews", 0), reverse=True)
        for uname, udata in sorted_users[:30]:
            avg_str = f", Avg Rating: {udata['avg_rating_given']}/5" if udata.get("avg_rating_given") else ""
            lines.append(f"### 👤 `{uname}` ({udata['total_reviews']} review(s){avg_str})")
            for pr in udata.get("products_reviewed", [])[:5]:
                r = f"⭐ [{pr.get('rating', '?')}/5]" if pr.get("rating") else ""
                comm = pr.get('comment', '').replace('\n', ' ')
                dt = pr.get('date', 'Unknown')
                f_src = pr.get('file', '')
                p_name = pr.get('product', '?')
                lines.append(f"- **{p_name}** {r} ({dt}): '_{comm}_' (File: `{f_src}`)")
            lines.append("")
    else:
        lines.append("_No user reviews detected on these pages._\n")

    # 4. Per-Page Details
    lines.append("## 4. Per-Page Extracted Intelligence")
    for page in pages:
        fname = page.get("file", "unknown")
        ptype = page.get("page_type", "GENERAL")
        summary = page.get("summary", "")
        icon = {"PRODUCT_DETAIL": "📦", "CATALOG_LISTING": "📋", "GENERAL": "📄"}.get(ptype, "📄")

        lines.append(f"### {icon} `{fname}` — `{ptype}`")
        if summary:
            lines.append(f"> **Summary:** {summary}\n")

        prod = page.get("product")
        if prod and prod.get("title"):
            prices = prod.get("prices") or {}
            p_val = prices.get("current") or prices.get("listed") or "N/A"
            lines.append(f"- **Product:** **{prod['title']}** (${p_val})")
            if prod.get("category"):
                lines.append(f"- **Category:** {prod['category']}")
            if prod.get("overall_rating"):
                lines.append(f"- **Rating:** {prod['overall_rating']}/5 ({prod.get('review_count', 0)} reviews)")

        revs = page.get("reviews") or []
        if revs:
            lines.append(f"- **Customer Reviews ({len(revs)}):**")
            for r in revs[:3]:
                r_rating = f"[{r.get('rating')}/5]" if r.get('rating') else ""
                lines.append(f"  • **{r.get('author')}** {r_rating} ({r.get('date')}): _{r.get('comment','')[:80]}_")

        lines.append("")

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "intel_report.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return out_path
