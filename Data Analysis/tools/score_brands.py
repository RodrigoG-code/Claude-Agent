"""
score_brands.py
---------------
Evaluates each brand's metrics and assigns per-metric flags (Good/Average/Poor)
and an overall brand flag, using a multi-signal scoring algorithm.

Scoring signals per metric:
  1. Sector threshold (from config/brands.json)      weight: 0.35
  2. Universal benchmark (from config/benchmarks.json) weight: 0.35
  3. Month-over-month trend                           weight: 0.15
  4. Peer rank (top/middle/bottom third)              weight: 0.15

Usage:
    .venv/bin/python tools/score_brands.py --year 2026 --month 3

Inputs:
    .tmp/processed/metrics_YYYY_MM.json
    config/brands.json
    config/benchmarks.json

Outputs:
    .tmp/processed/peer_ranks_YYYY_MM.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_config import get_thresholds, get_benchmark, get_brand

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / ".tmp" / "processed"

OVERALL_WEIGHTS = {
    "conversion_rate":       0.20,
    "total_sales":           0.15,
    "clv":                   0.15,
    "cart_abandonment_rate": 0.10,
    "aov":                   0.08,
    "churn":                 0.05,
    "add_to_cart_rate":      0.05,
    "sessions":              0.07,
    "refund_rate":           0.05,
    "repeat_purchase_rate":  0.05,
    "total_orders":          0.05,
}

LOWER_IS_BETTER = {"cart_abandonment_rate", "churn", "refund_rate"}

ALL_METRICS = ["total_sales", "conversion_rate", "aov", "add_to_cart_rate",
               "cart_abandonment_rate", "clv", "churn",
               "sessions", "refund_rate", "repeat_purchase_rate", "total_orders"]

FLAG_THRESHOLDS = {"good": 1.5, "poor": 0.8}


def threshold_score(value, good, poor, lower_is_better=False):
    if value is None or good in (None, "") or poor in (None, ""):
        return None
    value, good, poor = float(value), float(good), float(poor)
    if lower_is_better:
        return 2.0 if value <= good else (1.0 if value <= poor else 0.0)
    return 2.0 if value >= good else (1.0 if value >= poor else 0.0)


def trend_score(mom_pct, lower_is_better=False):
    if mom_pct is None:
        return None
    improving = mom_pct > 2.0
    declining = mom_pct < -2.0
    if lower_is_better:
        improving, declining = declining, improving
    return 0.5 if improving else (-0.5 if declining else 0.0)


def peer_score_from_rank(rank, total, lower_is_better=False):
    if rank is None or not total or total < 5:
        return None
    pct = rank / total
    in_top = pct <= 0.33
    in_bottom = pct > 0.67
    return 0.5 if in_top else (-0.5 if in_bottom else 0.0)


def flag_from_score(score):
    if score is None:
        return "Unknown"
    return "Good" if score >= FLAG_THRESHOLDS["good"] else ("Average" if score >= FLAG_THRESHOLDS["poor"] else "Poor")


def compute_metric_score(value, mom_pct, peer_rank, total_brands,
                         good_threshold, poor_threshold,
                         benchmark_good, benchmark_poor,
                         lower_is_better=False):
    signals = [
        (threshold_score(value, good_threshold, poor_threshold, lower_is_better), 0.35),
        (threshold_score(value, benchmark_good, benchmark_poor, lower_is_better), 0.35),
        (trend_score(mom_pct, lower_is_better), 0.15),
        (peer_score_from_rank(peer_rank, total_brands, lower_is_better), 0.15),
    ]
    valid = [(s, w) for s, w in signals if s is not None]
    if not valid:
        return {"score": None, "flag": "Unknown"}
    tw = sum(w for _, w in valid)
    score = sum(s * (w / tw) for s, w in valid)
    return {"score": round(score, 4), "flag": flag_from_score(score)}


def compute_peer_ranks(brands, metric, lower_is_better=False):
    values = [(b["brand_id"], b.get(metric)) for b in brands if b.get(metric) is not None]
    sorted_vals = sorted(values, key=lambda x: x[1], reverse=not lower_is_better)
    return {brand_id: rank + 1 for rank, (brand_id, _) in enumerate(sorted_vals)}


def main():
    parser = argparse.ArgumentParser(description="Score brands and assign performance flags.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    args = parser.parse_args()

    input_path = PROCESSED_DIR / f"metrics_{args.year}_{args.month:02d}.json"
    if not input_path.exists():
        print(f"ERROR: {input_path} not found. Run merge_metrics.py first.")
        sys.exit(1)

    with open(input_path) as f:
        brands = json.load(f)

    total_brands = len(brands)
    print(f"Scoring {total_brands} brands...")

    # Pre-compute peer ranks
    peer_ranks = {}
    for metric in ALL_METRICS:
        peer_ranks[metric] = compute_peer_ranks(brands, metric, metric in LOWER_IS_BETTER)

    scored = []
    for brand in brands:
        brand_id = brand["brand_id"]
        sector = brand.get("sector", "")
        brand_config = get_brand(brand_id)

        brand_result = {**brand}
        metric_scores = {}

        for metric in ALL_METRICS:
            lb = metric in LOWER_IS_BETTER
            thresholds = get_thresholds(brand_config, metric)
            bm = get_benchmark(sector, metric)

            mom_key = f"{metric}_mom_pct"

            result = compute_metric_score(
                value=brand.get(metric),
                mom_pct=brand.get(mom_key),
                peer_rank=peer_ranks[metric].get(brand_id),
                total_brands=total_brands,
                good_threshold=thresholds.get("good"),
                poor_threshold=thresholds.get("poor"),
                benchmark_good=bm.get("good"),
                benchmark_poor=bm.get("poor"),
                lower_is_better=lb,
            )
            brand_result[f"{metric}_flag"] = result["flag"]
            brand_result[f"{metric}_score"] = result["score"]
            brand_result[f"peer_rank_{metric}"] = peer_ranks[metric].get(brand_id)
            metric_scores[metric] = result["score"]

        # Overall score
        overall_signals = [(metric_scores[m], w) for m, w in OVERALL_WEIGHTS.items()
                           if metric_scores.get(m) is not None]
        if overall_signals:
            tw = sum(w for _, w in overall_signals)
            overall_score = sum(s * (w / tw) for s, w in overall_signals)
        else:
            overall_score = None

        brand_result["overall_score"] = round(overall_score, 4) if overall_score is not None else None
        brand_result["overall_flag"] = flag_from_score(overall_score)
        brand_result["peer_rank_overall"] = None
        scored.append(brand_result)

    # Peer rank on overall score
    overall_ranks = compute_peer_ranks(
        [{"brand_id": b["brand_id"], "overall_score": b["overall_score"]} for b in scored],
        "overall_score",
    )
    for brand in scored:
        brand["peer_rank_overall"] = overall_ranks.get(brand["brand_id"])

    output_path = PROCESSED_DIR / f"peer_ranks_{args.year}_{args.month:02d}.json"
    with open(output_path, "w") as f:
        json.dump(scored, f, indent=2)

    flag_counts = {"Good": 0, "Average": 0, "Poor": 0, "Unknown": 0}
    for b in scored:
        flag_counts[b["overall_flag"]] += 1

    print(f"Done: {output_path}")
    print(f"  Good: {flag_counts['Good']} | Average: {flag_counts['Average']} | Poor: {flag_counts['Poor']}")


if __name__ == "__main__":
    main()
