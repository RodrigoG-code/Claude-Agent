"""
merge_metrics.py
----------------
Processes Napps raw data into a unified metrics snapshot per brand.
Also loads the previous month's local snapshot to compute MoM deltas.

Usage:
    .venv/bin/python tools/merge_metrics.py --year 2026 --month 3

Inputs:
    .tmp/raw/napps/{brand_id}_YYYY_MM.json
    data/snapshots/{prev_year}_{prev_month:02d}.json (for MoM deltas)

Outputs:
    .tmp/processed/metrics_YYYY_MM.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_config import load_snapshot_as_dict

BASE_DIR = Path(__file__).resolve().parent.parent
NAPPS_DIR = BASE_DIR / ".tmp" / "raw" / "napps"
PROCESSED_DIR = BASE_DIR / ".tmp" / "processed"

ALL_METRICS = ["total_sales", "conversion_rate", "aov", "add_to_cart_rate",
               "cart_abandonment_rate", "clv", "churn",
               "sessions", "refund_rate", "repeat_purchase_rate", "total_orders"]


def prev_month(year: int, month: int) -> tuple:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def mom_pct(current, previous):
    try:
        c, p = float(current), float(previous)
        if p == 0:
            return None
        return round(((c - p) / abs(p)) * 100, 2)
    except (TypeError, ValueError):
        return None


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main():
    parser = argparse.ArgumentParser(description="Process Napps data into unified snapshot.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    args = parser.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    period = f"{args.year}-{args.month:02d}"
    suffix = f"{args.year}_{args.month:02d}.json"

    napps_files = {f.stem.replace(f"_{args.year}_{args.month:02d}", ""): f
                   for f in NAPPS_DIR.glob(f"*_{suffix}")}

    if not napps_files:
        print(f"ERROR: No raw files found for {period}. Run fetch_napps.py first.")
        sys.exit(1)

    py, pm = prev_month(args.year, args.month)
    print(f"Loading previous month snapshot ({py}-{pm:02d}) for MoM deltas...")
    prev_snapshots = load_snapshot_as_dict(py, pm)
    if not prev_snapshots:
        print("  No prior snapshot found — MoM deltas will be skipped for this run.")

    print(f"Processing data for {len(napps_files)} brand(s)...")
    merged = []
    warnings = []

    for brand_id in sorted(napps_files):
        napps = load_json(napps_files[brand_id])
        has_napps = bool(napps) and "error" not in napps

        if not has_napps:
            warnings.append(f"{brand_id}: missing/errored Napps data")

        prev = prev_snapshots.get(brand_id, {})

        record = {
            "brand_id": brand_id,
            "brand_name": napps.get("brand_name", brand_id),
            "sector": napps.get("sector", ""),
            "period": period,
            "data_complete": has_napps,
        }

        for metric in ALL_METRICS:
            current_val = napps.get(metric) if has_napps else None
            prev_val = prev.get(metric)
            record[metric] = current_val
            record[f"{metric}_prev"] = prev_val
            record[f"{metric}_mom_pct"] = mom_pct(current_val, prev_val)

        merged.append(record)

    output_path = PROCESSED_DIR / f"metrics_{args.year}_{args.month:02d}.json"
    with open(output_path, "w") as f:
        json.dump(merged, f, indent=2)

    print(f"Written: {output_path}")
    complete = sum(1 for b in merged if b["data_complete"])
    print(f"Brands: {len(merged)} | Complete: {complete}/{len(merged)}")

    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  ! {w}")


if __name__ == "__main__":
    main()
