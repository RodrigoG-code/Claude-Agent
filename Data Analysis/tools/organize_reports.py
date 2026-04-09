"""
organize_reports.py
-------------------
Copies the generated PDFs and Excel file from .tmp/ into outputs/YYYY_MM/,
creating a clean, permanent output folder for each month.

Usage:
    .venv/bin/python tools/organize_reports.py --year 2026 --month 3

Inputs:
    .tmp/reports/pdf/{brand_id}_YYYY_MM.pdf
    .tmp/reports/excel/brand_performance_YYYY_MM.xlsx

Outputs:
    outputs/YYYY_MM/{brand_id}_YYYY_MM.pdf
    outputs/YYYY_MM/brand_performance_YYYY_MM.xlsx
"""

import argparse
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PDF_DIR = BASE_DIR / ".tmp" / "reports" / "pdf"
EXCEL_DIR = BASE_DIR / ".tmp" / "reports" / "excel"
OUTPUTS_BASE = BASE_DIR / "outputs"


def main():
    parser = argparse.ArgumentParser(description="Copy reports to outputs/YYYY_MM/.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    args = parser.parse_args()

    period = f"{args.year}_{args.month:02d}"
    output_dir = OUTPUTS_BASE / period
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(PDF_DIR.glob(f"*_{period}.pdf"))
    excel_file = EXCEL_DIR / f"brand_performance_{period}.xlsx"

    if not pdf_files and not excel_file.exists():
        print(f"ERROR: No reports found in .tmp/ for {period}. Run render_pdf.py and render_excel.py first.")
        sys.exit(1)

    copied = 0
    for pdf in pdf_files:
        dest = output_dir / pdf.name
        shutil.copy2(pdf, dest)
        copied += 1

    if excel_file.exists():
        shutil.copy2(excel_file, output_dir / excel_file.name)
        print(f"Copied {copied} PDFs + 1 Excel → outputs/{period}/")
    else:
        print(f"Copied {copied} PDFs (no Excel found) → outputs/{period}/")

    print(f"Output folder: {output_dir}")


if __name__ == "__main__":
    main()
