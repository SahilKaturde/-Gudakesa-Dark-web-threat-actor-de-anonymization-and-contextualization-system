"""
extractor/aggregator.py
Cross-page intelligence synthesis with strict deduplication:
- Vendor Dossiers (unique products per vendor with occurrence tracking)
- User Profiles (consolidated reviews by distinct usernames)
"""
from typing import Any, Dict, List
from collections import defaultdict


def _normalize_title(title: str) -> str:
    """Normalize product title for strict deduplication."""
    if not title:
        return ""
    t = title.lower().strip()
    import re
    t = re.sub(r"\s+", " ", t)
    return t


def aggregate_vendors(all_pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate vendor information with strict product deduplication."""
    vendors: Dict[str, Dict[str, Any]] = {}

    for page in all_pages:
        page_file = page.get("file", "")
        page_type = page.get("page_type", "")

        if page_type == "PRODUCT_DETAIL":
            vendor = page.get("vendor")
            prod = page.get("product")
            if vendor and vendor.get("name"):
                vname = vendor["name"]
                if vname not in vendors:
                    vendors[vname] = {
                        "vendor_name": vname,
                        "vendor_type": vendor.get("type", "marketplace_vendor"),
                        "rating": vendor.get("rating"),
                        "contacts": vendor.get("contacts") or {},
                        "crypto_accepted": set(vendor.get("crypto_accepted") or []),
                        "products_map": {},
                        "categories": set(),
                        "pages_found_on": set(),
                    }

                v = vendors[vname]
                if vendor.get("rating") and not v["rating"]:
                    v["rating"] = vendor["rating"]
                if vendor.get("contacts"):
                    v["contacts"].update(vendor["contacts"])
                if vendor.get("crypto_accepted"):
                    v["crypto_accepted"].update(vendor["crypto_accepted"])
                v["pages_found_on"].add(page_file)

                if prod and prod.get("title"):
                    norm = _normalize_title(prod["title"])
                    prices = prod.get("prices") or {}
                    p_val = prices.get("current") or prices.get("listed") or (f"${prices['range_low']}-${prices['range_high']}" if prices.get("range_low") else "N/A")
                    if not p_val.startswith("$") and p_val != "N/A":
                        p_val = f"${p_val}"

                    if norm not in v["products_map"]:
                        v["products_map"][norm] = {
                            "title": prod["title"],
                            "price": p_val,
                            "category": prod.get("category"),
                            "found_in_pages": [page_file],
                            "occurrence_count": 1,
                        }
                    else:
                        v["products_map"][norm]["occurrence_count"] += 1
                        if page_file not in v["products_map"][norm]["found_in_pages"]:
                            v["products_map"][norm]["found_in_pages"].append(page_file)

                    if prod.get("category"):
                        v["categories"].add(prod["category"])

        elif page_type == "CATALOG_LISTING":
            catalog_items = page.get("catalog_products") or []
            page_vendor = page.get("vendor")

            for cp in catalog_items:
                vname = cp.get("vendor") or (page_vendor.get("name") if page_vendor else None)
                if not vname:
                    continue

                if vname not in vendors:
                    vendors[vname] = {
                        "vendor_name": vname,
                        "vendor_type": "marketplace_vendor",
                        "rating": cp.get("rating"),
                        "contacts": {},
                        "crypto_accepted": set(),
                        "products_map": {},
                        "categories": set(),
                        "pages_found_on": set(),
                    }

                v = vendors[vname]
                v["pages_found_on"].add(page_file)
                if cp.get("rating") and not v["rating"]:
                    v["rating"] = cp["rating"]

                title = cp.get("title", "")
                if title:
                    norm = _normalize_title(title)
                    price = cp.get("price") or "N/A"
                    if norm not in v["products_map"]:
                        v["products_map"][norm] = {
                            "title": title,
                            "price": price,
                            "category": cp.get("category"),
                            "found_in_pages": [page_file],
                            "occurrence_count": 1,
                        }
                    else:
                        v["products_map"][norm]["occurrence_count"] += 1
                        if page_file not in v["products_map"][norm]["found_in_pages"]:
                            v["products_map"][norm]["found_in_pages"].append(page_file)

                    if cp.get("category"):
                        v["categories"].add(cp["category"])

    result = {}
    for vname, vdata in vendors.items():
        unique_products = list(vdata["products_map"].values())
        result[vname] = {
            "vendor_name": vname,
            "vendor_type": vdata["vendor_type"],
            "rating": vdata["rating"],
            "contacts": vdata["contacts"],
            "crypto_accepted": sorted(vdata["crypto_accepted"]),
            "product_count": len(unique_products),
            "unique_products": sorted(unique_products, key=lambda x: x.get("occurrence_count", 0), reverse=True),
            "categories": sorted(vdata["categories"]),
            "pages_found_on": sorted(vdata["pages_found_on"]),
        }

    return result


def aggregate_users(all_pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate reviewer profiles across all pages."""
    users: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "username": "",
        "total_reviews": 0,
        "ratings_given": [],
        "products_reviewed": [],
    })

    for page in all_pages:
        reviews = page.get("reviews") or []
        prod = page.get("product") or {}
        prod_title = prod.get("title") or "Unknown Product"

        for rev in reviews:
            author = rev.get("author") or rev.get("username")
            if not author or author.lower() in ["anonymous", "none", "n/a"]:
                continue

            u = users[author]
            u["username"] = author
            u["total_reviews"] += 1

            if rev.get("rating") is not None:
                u["ratings_given"].append(rev["rating"])

            u["products_reviewed"].append({
                "product": prod_title,
                "rating": rev.get("rating"),
                "date": rev.get("date", ""),
                "comment": rev.get("comment", ""),
                "file": page.get("file", ""),
            })

    result = {}
    for username, data in users.items():
        ratings = data.pop("ratings_given", [])
        data["avg_rating_given"] = (
            round(sum(ratings) / len(ratings), 2) if ratings else None
        )
        dates = [p["date"] for p in data["products_reviewed"] if p.get("date") and p.get("date") != "Unknown"]
        if dates:
            data["activity_dates"] = sorted(dates)
        result[username] = data

    return result


def aggregate_all(all_pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Execute full aggregation pipeline."""
    return {
        "vendor_dossiers": aggregate_vendors(all_pages),
        "user_profiles": aggregate_users(all_pages),
    }
