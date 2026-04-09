"""
fetch_napps.py
--------------
Pulls conversion rate, AOV, add-to-cart rate, cart abandonment rate, CLV, and churn
from the Napps REST API for each active brand.

Usage:
    .venv/bin/python tools/fetch_napps.py --year 2026 --month 3
    .venv/bin/python tools/fetch_napps.py --year 2026 --month 3 --brand-id acme-uk

Outputs:
    .tmp/raw/napps/{brand_id}_YYYY_MM.json per brand

TODO: Confirm the following with Napps API documentation before first run:
    1. NAPPS_AUTH_URL — the OAuth2 token endpoint
    2. NAPPS_API_BASE — the base URL for analytics endpoints
    3. NAPPS_METRICS_ENDPOINT — the path that returns the 6 required metrics
    4. The exact JSON field names in the response for each metric
    5. Whether date ranges are passed as query params or request body
"""

import argparse
import json
import os
import sys
from calendar import monthrange
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_config import load_brands

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / ".tmp" / "raw" / "napps"

# TODO: Replace with actual Napps API URLs once confirmed from docs
NAPPS_AUTH_URL = "https://api.napps.com/oauth/token"      # TODO: confirm
NAPPS_API_BASE = "https://api.napps.com/v1"               # TODO: confirm
NAPPS_METRICS_ENDPOINT = "/analytics/metrics"             # TODO: confirm

# TODO: Update keys to match actual Napps API response field names
FIELD_MAP = {
    "total_sales":           "total_sales",           # TODO: confirm
    "conversion_rate":       "conversion_rate",       # TODO: confirm
    "average_order_value":   "aov",                   # TODO: confirm
    "add_to_cart_rate":      "add_to_cart_rate",      # TODO: confirm
    "cart_abandonment_rate": "cart_abandonment_rate", # TODO: confirm
    "customer_lifetime_value": "clv",                 # TODO: confirm
    "churn_rate":            "churn",                 # TODO: confirm
    "sessions":              "sessions",              # TODO: confirm
    "refund_rate":           "refund_rate",           # TODO: confirm
    "repeat_purchase_rate":  "repeat_purchase_rate",  # TODO: confirm
    "total_orders":          "total_orders",          # TODO: confirm
}


def get_napps_token(client_id: str, client_secret: str) -> str:
    response = requests.post(
        NAPPS_AUTH_URL,
        data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Napps auth failed ({response.status_code}): {response.text[:200]}")
    return response.json()["access_token"]


def fetch_brand_metrics(brand: dict, year: int, month: int) -> dict:
    brand_id = brand["brand_id"]
    client_id = os.environ.get(brand["napps_client_id_key"])
    client_secret = os.environ.get(brand["napps_client_secret_key"])

    if not client_id or not client_secret:
        missing = [k for k, v in {brand["napps_client_id_key"]: client_id,
                                   brand["napps_client_secret_key"]: client_secret}.items() if not v]
        return {"brand_id": brand_id, "period": f"{year}-{month:02d}",
                "error": f"Missing env vars: {', '.join(missing)}"}

    _, last_day = monthrange(year, month)
    date_from = date(year, month, 1).isoformat()
    date_to = date(year, month, last_day).isoformat()

    try:
        token = get_napps_token(client_id, client_secret)
    except RuntimeError as e:
        return {"brand_id": brand_id, "period": f"{year}-{month:02d}", "error": str(e)}

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    # TODO: Adjust params/body structure to match actual Napps API spec
    params = {"date_from": date_from, "date_to": date_to, "brand_id": brand_id}

    response = requests.get(NAPPS_API_BASE + NAPPS_METRICS_ENDPOINT,
                            headers=headers, params=params, timeout=30)

    if response.status_code != 200:
        return {"brand_id": brand_id, "period": f"{year}-{month:02d}",
                "error": f"HTTP {response.status_code}: {response.text[:200]}"}

    raw = response.json()
    metrics = {}
    for napps_field, our_field in FIELD_MAP.items():
        value = raw.get(napps_field) or raw.get("data", {}).get(napps_field)
        metrics[our_field] = round(float(value), 4) if value is not None else None

    return {
        "brand_id": brand_id,
        "brand_name": brand.get("brand_name", brand_id),
        "sector": brand.get("sector", ""),
        "period": f"{year}-{month:02d}",
        **metrics,
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch Napps metrics per brand.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--brand-id", type=str, default=None)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    brands = load_brands(args.brand_id)
    if not brands:
        print("No active brands found. Exiting.")
        sys.exit(1)

    print(f"Fetching Napps metrics for {len(brands)} brand(s) — {args.year}-{args.month:02d}")

    errors = []
    for brand in brands:
        brand_id = brand["brand_id"]
        print(f"  → {brand_id}...", end=" ", flush=True)
        result = fetch_brand_metrics(brand, args.year, args.month)

        output_path = OUTPUT_DIR / f"{brand_id}_{args.year}_{args.month:02d}.json"
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)

        if "error" in result:
            print(f"ERROR: {result['error']}")
            errors.append(brand_id)
        else:
            print(f"conv={result.get('conversion_rate')}% | AOV={result.get('aov')}")

    print(f"\nDone. {len(brands) - len(errors)}/{len(brands)} successful.")
    if errors:
        print(f"Failed: {', '.join(errors)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
