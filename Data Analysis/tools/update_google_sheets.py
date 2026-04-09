"""
update_google_sheets.py
-----------------------
Appends this month's scored brand data to the 'monthly_snapshots' sheet.
Idempotent: skips any brand that already has a row for the given period.

Usage:
    python tools/update_google_sheets.py --year 2026 --month 3

Inputs:
    .tmp/processed/peer_ranks_YYYY_MM.json

Outputs:
    Appended rows in the 'monthly_snapshots' Google Sheet
"""

import argparse
import json
import os
import sys
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / ".tmp" / "processed"

SNAPSHOT_COLUMNS = [
    "snapshot_date",
    "brand_id",
    "brand_name",
    "sector",
    "total_sales",
    "conversion_rate",
    "aov",
    "add_to_cart_rate",
    "cart_abandonment_rate",
    "clv",
    "churn",
    "sales_mom_pct",
    "conversion_rate_mom_pct",
    "aov_mom_pct",
    "add_to_cart_mom_pct",
    "cart_abandonment_mom_pct",
    "clv_mom_pct",
    "churn_mom_pct",
    "overall_flag",
    "conversion_rate_flag",
    "aov_flag",
    "add_to_cart_rate_flag",
    "cart_abandonment_rate_flag",
    "clv_flag",
    "churn_flag",
    "peer_rank_sales",
    "peer_rank_conversion_rate",
    "peer_rank_overall",
    "pdf_url",
    "excel_url",
]


def get_sheets_client():
    creds = Credentials.from_service_account_file(
        BASE_DIR / "credentials.json", scopes=SCOPES
    )
    return gspread.authorize(creds)


def load_url_index(year: int, month: int) -> dict:
    """Load PDF/Excel URLs written by upload_reports.py, if available."""
    url_index_path = BASE_DIR / ".tmp" / "reports" / f"url_index_{year}_{month:02d}.json"
    if url_index_path.exists():
        with open(url_index_path) as f:
            return json.load(f)
    return {}


def get_existing_keys(worksheet) -> set:
    """Return a set of (brand_id, snapshot_date) already in the sheet."""
    records = worksheet.get_all_records()
    return {(r["brand_id"], r["snapshot_date"]) for r in records}


def main():
    parser = argparse.ArgumentParser(description="Append monthly snapshot to Google Sheets.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    args = parser.parse_args()

    snapshot_date = f"{args.year}-{args.month:02d}-01"
    input_path = PROCESSED_DIR / f"peer_ranks_{args.year}_{args.month:02d}.json"

    if not input_path.exists():
        print(f"ERROR: {input_path} not found. Run score_brands.py first.")
        sys.exit(1)

    with open(input_path) as f:
        brands = json.load(f)

    url_index = load_url_index(args.year, args.month)

    print("Connecting to Google Sheets...")
    client = get_sheets_client()
    sheet_id = os.environ["GOOGLE_SHEETS_ID"]
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.worksheet("monthly_snapshots")

    # Ensure header row exists
    existing_data = worksheet.get_all_values()
    if not existing_data:
        worksheet.append_row(SNAPSHOT_COLUMNS)
        existing_keys = set()
    else:
        existing_keys = get_existing_keys(worksheet)

    rows_to_append = []
    skipped = []

    for brand in brands:
        brand_id = brand["brand_id"]
        key = (brand_id, snapshot_date)

        if key in existing_keys:
            skipped.append(brand_id)
            continue

        # Resolve PDF and Excel URLs from the upload index
        brand_urls = url_index.get(brand_id, {})
        pdf_url = brand_urls.get("pdf_url", "")
        excel_url = url_index.get("excel_url", "")  # Excel is one file for all brands

        row = [
            snapshot_date,
            brand_id,
            brand.get("brand_name", ""),
            brand.get("sector", ""),
            brand.get("total_sales", ""),
            brand.get("conversion_rate", ""),
            brand.get("aov", ""),
            brand.get("add_to_cart_rate", ""),
            brand.get("cart_abandonment_rate", ""),
            brand.get("clv", ""),
            brand.get("churn", ""),
            brand.get("sales_mom_pct", ""),
            brand.get("conversion_rate_mom_pct", ""),
            brand.get("aov_mom_pct", ""),
            brand.get("add_to_cart_mom_pct", ""),
            brand.get("cart_abandonment_mom_pct", ""),
            brand.get("clv_mom_pct", ""),
            brand.get("churn_mom_pct", ""),
            brand.get("overall_flag", ""),
            brand.get("conversion_rate_flag", ""),
            brand.get("aov_flag", ""),
            brand.get("add_to_cart_rate_flag", ""),
            brand.get("cart_abandonment_rate_flag", ""),
            brand.get("clv_flag", ""),
            brand.get("churn_flag", ""),
            brand.get("peer_rank_sales", ""),
            brand.get("peer_rank_conversion_rate", ""),
            brand.get("peer_rank_overall", ""),
            pdf_url,
            excel_url,
        ]
        rows_to_append.append(row)

    if rows_to_append:
        # Batch append all rows in one API call
        worksheet.append_rows(rows_to_append, value_input_option="USER_ENTERED")
        print(f"Appended {len(rows_to_append)} row(s) to monthly_snapshots.")
    else:
        print("No new rows to append.")

    if skipped:
        print(f"Skipped (already present): {', '.join(skipped)}")

    print("Done.")


if __name__ == "__main__":
    main()
