"""
upload_reports.py
-----------------
Uploads all brand PDFs and the Excel file to a Google Drive folder,
sets shareable links, and writes a URL index for downstream tools.

Usage:
    python tools/upload_reports.py --year 2026 --month 3

Inputs:
    .tmp/reports/pdf/{brand_id}_YYYY_MM.pdf (all brand PDFs)
    .tmp/reports/excel/brand_performance_YYYY_MM.xlsx

Outputs:
    .tmp/reports/url_index_YYYY_MM.json
    Files uploaded to Google Drive under: Brand Reports/YYYY-MM/
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/drive",
]

BASE_DIR = Path(__file__).resolve().parent.parent
PDF_DIR = BASE_DIR / ".tmp" / "reports" / "pdf"
EXCEL_DIR = BASE_DIR / ".tmp" / "reports" / "excel"
REPORTS_DIR = BASE_DIR / ".tmp" / "reports"

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}


def get_drive_service():
    creds = Credentials.from_service_account_file(
        BASE_DIR / "credentials.json", scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


def get_or_create_folder(service, name: str, parent_id: str) -> str:
    """Get an existing folder by name under parent, or create it."""
    query = (
        f"name='{name}' and mimeType='application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    folder_metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=folder_metadata, fields="id").execute()
    return folder["id"]


def set_anyone_reader(service, file_id: str):
    """Make the file readable by anyone with the link."""
    service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
    ).execute()


def get_shareable_link(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"


def upload_file(service, local_path: Path, folder_id: str, mime_type: str) -> str:
    """Upload a file and return its Drive file ID."""
    file_metadata = {
        "name": local_path.name,
        "parents": [folder_id],
    }
    media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=False)
    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id",
    ).execute()
    return uploaded["id"]


def main():
    parser = argparse.ArgumentParser(description="Upload reports to Google Drive.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    args = parser.parse_args()

    root_folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    if not root_folder_id:
        print("ERROR: GOOGLE_DRIVE_FOLDER_ID not set in .env")
        sys.exit(1)

    period = f"{args.year}-{args.month:02d}"
    period_label = f"{MONTH_NAMES[args.month]} {args.year}"

    pdf_files = sorted(PDF_DIR.glob(f"*_{args.year}_{args.month:02d}.pdf"))
    excel_file = EXCEL_DIR / f"brand_performance_{args.year}_{args.month:02d}.xlsx"

    if not pdf_files:
        print(f"WARNING: No PDF files found in {PDF_DIR} for {period}")
    if not excel_file.exists():
        print(f"WARNING: Excel file not found: {excel_file}")

    print("Connecting to Google Drive...")
    service = get_drive_service()

    # Create month folder: Brand Reports / YYYY-MM (Month Year)
    brand_reports_folder = get_or_create_folder(service, "Brand Reports", root_folder_id)
    month_folder_name = f"{period} ({period_label})"
    month_folder_id = get_or_create_folder(service, month_folder_name, brand_reports_folder)
    print(f"Drive folder: Brand Reports / {month_folder_name}")

    url_index = {}
    errors = []

    # Upload PDFs
    print(f"\nUploading {len(pdf_files)} PDFs...")
    for pdf_path in pdf_files:
        # Extract brand_id from filename: {brand_id}_YYYY_MM.pdf
        brand_id = pdf_path.stem.replace(f"_{args.year}_{args.month:02d}", "")
        print(f"  → {brand_id}...", end=" ", flush=True)
        try:
            file_id = upload_file(service, pdf_path, month_folder_id, "application/pdf")
            set_anyone_reader(service, file_id)
            url_index[brand_id] = {"pdf_url": get_shareable_link(file_id)}
            print("OK")
        except Exception as e:
            print(f"ERROR: {e}")
            errors.append(f"PDF {brand_id}: {e}")

    # Upload Excel
    if excel_file.exists():
        print(f"\nUploading Excel: {excel_file.name}...", end=" ", flush=True)
        try:
            excel_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            file_id = upload_file(service, excel_file, month_folder_id, excel_mime)
            set_anyone_reader(service, file_id)
            excel_url = get_shareable_link(file_id)
            url_index["excel_url"] = excel_url
            print("OK")
        except Exception as e:
            print(f"ERROR: {e}")
            errors.append(f"Excel: {e}")

    # Write URL index
    url_index_path = REPORTS_DIR / f"url_index_{args.year}_{args.month:02d}.json"
    with open(url_index_path, "w") as f:
        json.dump(url_index, f, indent=2)

    print(f"\nURL index written: {url_index_path}")
    print(f"Uploaded: {len(url_index) - (1 if 'excel_url' in url_index else 0)} PDFs + {'1 Excel' if 'excel_url' in url_index else '0 Excel'}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  ! {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
