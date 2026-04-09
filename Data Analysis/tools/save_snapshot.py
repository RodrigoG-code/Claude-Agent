"""
save_snapshot.py
----------------
Saves this month's scored brand data to data/snapshots/YYYY_MM.json.
This is the persistent historical record used by merge_metrics.py for MoM deltas.

Usage:
    .venv/bin/python tools/save_snapshot.py --year 2026 --month 3

Inputs:
    .tmp/processed/peer_ranks_YYYY_MM.json

Outputs:
    data/snapshots/YYYY_MM.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_config import save_snapshot, load_snapshot

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / ".tmp" / "processed"


def main():
    parser = argparse.ArgumentParser(description="Save monthly snapshot to local data store.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    args = parser.parse_args()

    input_path = PROCESSED_DIR / f"peer_ranks_{args.year}_{args.month:02d}.json"
    if not input_path.exists():
        print(f"ERROR: {input_path} not found. Run score_brands.py first.")
        sys.exit(1)

    with open(input_path) as f:
        brands = json.load(f)

    # Check if snapshot already exists
    existing = load_snapshot(args.year, args.month)
    if existing:
        print(f"Snapshot for {args.year}-{args.month:02d} already exists ({len(existing)} brands). Overwriting...")

    save_snapshot(args.year, args.month, brands)
    print(f"Saved: data/snapshots/{args.year}_{args.month:02d}.json ({len(brands)} brands)")


if __name__ == "__main__":
    main()
