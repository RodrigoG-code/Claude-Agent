"""
fetch_shopify.py
----------------
Pulls total sales for a given month from the Shopify REST API for each active brand.

Usage:
    .venv/bin/python tools/fetch_shopify.py --year 2026 --month 3
    .venv/bin/python tools/fetch_shopify.py --year 2026 --month 3 --brand-id acme-uk

Outputs:
    .tmp/raw/shopify/{brand_id}_YYYY_MM.json per brand
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_config import load_brands

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / ".tmp" / "raw" / "shopify"


def fetch_brand_sales(brand: dict, year: int, month: int) -> dict:
    brand_id = brand["brand_id"]
    store_url = brand["shopify_store_url"].rstrip("/")
    token_key = brand["shopify_token_key"]
    token = os.environ.get(token_key)

    if not token:
        return {
            "brand_id": brand_id,
            "period": f"{year}-{month:02d}",
            "error": f"Missing env var: {token_key}",
        }

    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}
    base_url = f"https://{store_url}/admin/api/2024-01/orders.json"
    params = {
        "status": "any",
        "financial_status": "paid",
        "created_at_min": start.isoformat() + "T00:00:00Z",
        "created_at_max": end.isoformat() + "T00:00:00Z",
        "fields": "total_price",
        "limit": 250,
    }

    total_sales = 0.0
    order_count = 0
    page_info = None

    while True:
        if page_info:
            r = requests.get(base_url, headers=headers,
                             params={"limit": 250, "page_info": page_info, "fields": "total_price"},
                             timeout=30)
        else:
            r = requests.get(base_url, headers=headers, params=params, timeout=30)

        if r.status_code != 200:
            return {
                "brand_id": brand_id,
                "period": f"{year}-{month:02d}",
                "error": f"HTTP {r.status_code}: {r.text[:200]}",
            }

        for order in r.json().get("orders", []):
            total_sales += float(order.get("total_price", 0))
            order_count += 1

        link = r.headers.get("Link", "")
        if 'rel="next"' in link:
            for part in link.split(","):
                if 'rel="next"' in part:
                    page_info = part.split("page_info=")[1].split("&")[0].split(">")[0]
                    break
        else:
            break

    return {
        "brand_id": brand_id,
        "brand_name": brand.get("brand_name", brand_id),
        "sector": brand.get("sector", ""),
        "period": f"{year}-{month:02d}",
        "total_sales": round(total_sales, 2),
        "order_count": order_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch Shopify total sales per brand.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--brand-id", type=str, default=None)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    brands = load_brands(args.brand_id)
    if not brands:
        print("No active brands found. Exiting.")
        sys.exit(1)

    print(f"Fetching Shopify sales for {len(brands)} brand(s) — {args.year}-{args.month:02d}")

    errors = []
    for brand in brands:
        brand_id = brand["brand_id"]
        print(f"  → {brand_id}...", end=" ", flush=True)
        result = fetch_brand_sales(brand, args.year, args.month)

        output_path = OUTPUT_DIR / f"{brand_id}_{args.year}_{args.month:02d}.json"
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)

        if "error" in result:
            print(f"ERROR: {result['error']}")
            errors.append(brand_id)
        else:
            print(f"€{result['total_sales']:,.2f} ({result['order_count']} orders)")

    print(f"\nDone. {len(brands) - len(errors)}/{len(brands)} successful.")
    if errors:
        print(f"Failed: {', '.join(errors)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
