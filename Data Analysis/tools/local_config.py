"""
local_config.py
---------------
Shared utility for loading local config and historical data.
Replaces all Google Sheets reads.
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BRANDS_FILE = BASE_DIR / "config" / "brands.json"
BENCHMARKS_FILE = BASE_DIR / "config" / "benchmarks.json"
SNAPSHOTS_DIR = BASE_DIR / "data" / "snapshots"


def load_brands(brand_id_filter=None) -> list:
    """Load active brands from config/brands.json."""
    with open(BRANDS_FILE) as f:
        brands = json.load(f)
    brands = [b for b in brands if b.get("active", False)]
    if brand_id_filter:
        brands = [b for b in brands if b["brand_id"] == brand_id_filter]
    return brands


def get_brand(brand_id: str) -> dict:
    """Load a single brand config by ID."""
    with open(BRANDS_FILE) as f:
        brands = json.load(f)
    for b in brands:
        if b["brand_id"] == brand_id:
            return b
    return {}


def get_thresholds(brand: dict, metric: str) -> dict:
    """Return {'good': ..., 'poor': ...} thresholds for a brand+metric, or empty dict."""
    return brand.get("thresholds", {}).get(metric, {})


def load_benchmarks() -> dict:
    """Load config/benchmarks.json."""
    with open(BENCHMARKS_FILE) as f:
        return json.load(f)


def get_benchmark(sector: str, metric: str) -> dict:
    """Return benchmark dict for a sector+metric. Falls back to 'default'."""
    benchmarks = load_benchmarks()
    sector_data = benchmarks.get(sector, benchmarks.get("default", {}))
    return sector_data.get(metric, {})


def load_snapshot(year: int, month: int) -> list:
    """Load a monthly snapshot from data/snapshots/YYYY_MM.json. Returns [] if missing."""
    path = SNAPSHOTS_DIR / f"{year}_{month:02d}.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def load_snapshot_as_dict(year: int, month: int) -> dict:
    """Load a monthly snapshot as a dict keyed by brand_id."""
    records = load_snapshot(year, month)
    return {r["brand_id"]: r for r in records}


def save_snapshot(year: int, month: int, brands: list):
    """Write/overwrite a monthly snapshot to data/snapshots/YYYY_MM.json."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOTS_DIR / f"{year}_{month:02d}.json"
    with open(path, "w") as f:
        json.dump(brands, f, indent=2)
