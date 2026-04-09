"""
render_pdf.py
-------------
Generates a PDF report per brand using WeasyPrint + a Jinja2 HTML template.

Usage:
    .venv/bin/python tools/render_pdf.py --year 2026 --month 3
    .venv/bin/python tools/render_pdf.py --year 2026 --month 3 --brand-id acme-uk

Inputs:
    .tmp/processed/peer_ranks_YYYY_MM.json (must include insights)

Outputs:
    .tmp/reports/pdf/{brand_id}_YYYY_MM.pdf per brand
"""

import argparse
import base64
import json
import sys
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_config import get_brand, get_thresholds, get_benchmark

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / ".tmp" / "processed"
PDF_DIR = BASE_DIR / ".tmp" / "reports" / "pdf"
TEMPLATE_DIR = BASE_DIR / "tools" / "templates"

SECTOR_DISPLAY = {
    "fashion": "Fashion & Apparel",
    "fashion_apparel": "Fashion & Apparel",
    "beauty": "Beauty & Cosmetics",
    "beauty_cosmetics": "Beauty & Cosmetics",
    "electronics": "Electronics & Tech",
    "electronics_tech": "Electronics & Tech",
    "home": "Home & Living",
    "home_living": "Home & Living",
    "sports": "Sports & Outdoors",
    "sports_outdoors": "Sports & Outdoors",
    "food_beverage": "Food & Beverage",
    "luxury": "Luxury & Jewellery",
    "luxury_jewellery": "Luxury & Jewellery",
    "other": "Other",
}

NAPPS_METRIC_META = [
    {"key": "conversion_rate",       "label": "Conversion Rate",               "lower_is_better": False},
    {"key": "aov",                   "label": "Average Order Value (AOV)",     "lower_is_better": False},
    {"key": "add_to_cart_rate",      "label": "Add-to-Cart Rate",              "lower_is_better": False},
    {"key": "cart_abandonment_rate", "label": "Cart Abandonment Rate",         "lower_is_better": True},
    {"key": "clv",                   "label": "Customer Lifetime Value (CLV)", "lower_is_better": False},
    {"key": "churn",                 "label": "Churn Rate",                    "lower_is_better": True},
    {"key": "sessions",              "label": "Sessions / Traffic",            "lower_is_better": False},
    {"key": "refund_rate",           "label": "Refund / Return Rate",          "lower_is_better": True},
    {"key": "repeat_purchase_rate",  "label": "Repeat Purchase Rate",          "lower_is_better": False},
    {"key": "total_orders",          "label": "Number of Orders",              "lower_is_better": False},
]

FLAG_EMOJI = {"Good": "✅", "Average": "⚠️", "Poor": "❌", "Unknown": "❓"}
MONTH_NAMES = {1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
               7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"}


def fmt_currency(value):
    return f"€{float(value):,.2f}" if value is not None else "N/A"

def fmt_metric(value, key):
    if value is None:
        return "N/A"
    v = float(value)
    if key in {"conversion_rate", "add_to_cart_rate", "cart_abandonment_rate", "churn",
                "refund_rate", "repeat_purchase_rate"}:
        return f"{v:.2f}%"
    if key in {"aov", "clv"}:
        return f"€{v:,.2f}"
    if key in {"sessions", "total_orders"}:
        return f"{int(v):,}"
    return f"{v:,.2f}"

def fmt_mom(mom_pct):
    if mom_pct is None:
        return "—"
    v = float(mom_pct)
    arrow = "▲" if v > 0 else ("▼" if v < 0 else "→")
    return f"{arrow} {abs(v):.1f}%"

def mom_class(mom_pct, lower_is_better=False):
    if mom_pct is None:
        return "mom-flat"
    v = float(mom_pct)
    improving = v > 2
    declining = v < -2
    if lower_is_better:
        improving, declining = declining, improving
    return "mom-up" if improving else ("mom-down" if declining else "mom-flat")

def fmt_rank(rank, total):
    return f"#{rank} / {total}" if rank and total else "—"


def load_napps_logo_b64():
    logo_path = TEMPLATE_DIR / "assets" / "napps_logo.svg"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            return f"data:image/svg+xml;base64,{base64.b64encode(f.read()).decode()}"
    return ""


def build_cover_metrics(brand, napps_metrics, total_brands):
    """Build the 4-item cover scorecard list."""
    cover_keys = ["conversion_rate", "cart_abandonment_rate", "repeat_purchase_rate"]
    metrics = []
    # Total sales first
    mom_val = brand.get("sales_mom_pct")
    metrics.append({
        "label": "Total Sales",
        "value": fmt_currency(brand.get("total_sales")),
        "mom": fmt_mom(mom_val),
        "mom_dir": "up" if mom_val and mom_val > 0 else "down",
        "flag": "Good",
        "rank": f"#{brand.get('peer_rank_sales', '—')}/{total_brands}",
    })
    for m in napps_metrics:
        if m["key"] in cover_keys:
            mom_val = m.get("mom_pct")
            improving = mom_val and mom_val > 0
            if m.get("lower_is_better"):
                improving = mom_val and mom_val < 0
            metrics.append({
                "label": m["label"],
                "value": fmt_metric(m["value"], m["key"]),
                "mom": fmt_mom(mom_val),
                "mom_dir": "up" if improving else "down",
                "flag": m.get("flag", "Unknown"),
                "rank": f"#{m.get('peer_rank', '—')}/{total_brands}",
            })
    return metrics


def build_sessions_highlight(brand, total_brands):
    """Build the sessions hero block for the cover."""
    sessions = brand.get("sessions")
    if sessions is None:
        return None
    mom = brand.get("sessions_mom_pct")
    rank = brand.get("peer_rank_sessions")
    return {
        "label": "Sessions",
        "value": f"{int(sessions):,}",
        "mom": fmt_mom(mom),
        "rank": f"#{rank}" if rank else "—",
    }


def build_context(brand, year, month, total_brands):
    brand_id = brand["brand_id"]
    sector = brand.get("sector", "")
    brand_config = get_brand(brand_id)
    overall_flag = brand.get("overall_flag", "Unknown")

    napps_metrics = []
    for meta in NAPPS_METRIC_META:
        key = meta["key"]
        thresholds = get_thresholds(brand_config, key)
        bm = get_benchmark(sector, key)
        napps_metrics.append({
            **meta,
            "value": brand.get(key),
            "prev": brand.get(f"{key}_prev"),
            "mom_pct": brand.get(f"{key}_mom_pct"),
            "flag": brand.get(f"{key}_flag", "Unknown"),
            "peer_rank": brand.get(f"peer_rank_{key}"),
            "threshold_good": thresholds.get("good"),
            "threshold_poor": thresholds.get("poor"),
            "benchmark_good": bm.get("good"),
            "benchmark_poor": bm.get("poor"),
        })

    data_warnings = []
    if not brand.get("data_complete", True):
        data_warnings.append("Incomplete data for this period — some metrics may be missing.")
    for meta in NAPPS_METRIC_META:
        if brand.get(meta["key"]) is None:
            data_warnings.append(f"{meta['label']} data unavailable for this period.")

    return {
        "brand_id": brand_id,
        "brand_name": brand.get("brand_name", brand_id),
        "sector": sector,
        "sector_display": SECTOR_DISPLAY.get(sector, sector.replace("_", " ").title()),
        "brand_market": brand.get("market", ""),
        "period": brand.get("period", f"{year}-{month:02d}"),
        "period_label": f"{MONTH_NAMES[month]} {year}",
        "overall_flag": overall_flag,
        "flag_emoji": FLAG_EMOJI.get(overall_flag, ""),
        "total_sales": brand.get("total_sales"),
        "sales_prev": brand.get("sales_prev"),
        "sales_mom_pct": brand.get("sales_mom_pct"),
        "peer_rank_sales": brand.get("peer_rank_sales"),
        "peer_rank_overall": brand.get("peer_rank_overall"),
        "napps_logo_b64": load_napps_logo_b64(),
        "sessions_highlight": build_sessions_highlight(brand, total_brands),
        "cover_metrics": build_cover_metrics(brand, napps_metrics, total_brands),
        "napps_metrics": napps_metrics,
        "insights": brand.get("insights", {}),
        "total_brands": total_brands,
        "cover_headline": brand.get("cover_headline", ""),
        "data_warnings": data_warnings,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def render_brand_pdf(brand, year, month, total_brands):
    css_path = TEMPLATE_DIR / "report_styles.css"
    font_path = (TEMPLATE_DIR / "assets" / "fonts" / "PlayfairDisplay-Bold.ttf").resolve()
    font_face = f"""@font-face {{
    font-family: 'Playfair Display';
    src: url('file://{font_path}') format('truetype');
    font-weight: 700;
    font-style: normal;
}}
"""
    styles = font_face + css_path.read_text()

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    env.filters.update({
        "fmt_currency": fmt_currency,
        "fmt_metric": fmt_metric,
        "fmt_mom": fmt_mom,
        "mom_class": mom_class,
        "fmt_rank": fmt_rank,
    })

    context = build_context(brand, year, month, total_brands)
    context["styles"] = styles

    html_string = env.get_template("report_template.html").render(**context)
    output_path = PDF_DIR / f"{brand['brand_id']}_{year}_{month:02d}.pdf"
    HTML(string=html_string, base_url=str(TEMPLATE_DIR)).write_pdf(str(output_path))
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Render PDF reports per brand.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--brand-id", type=str, default=None)
    args = parser.parse_args()

    PDF_DIR.mkdir(parents=True, exist_ok=True)

    input_path = PROCESSED_DIR / f"peer_ranks_{args.year}_{args.month:02d}.json"
    if not input_path.exists():
        print(f"ERROR: {input_path} not found. Run generate_insights.py first.")
        sys.exit(1)

    with open(input_path) as f:
        brands = json.load(f)

    target = [b for b in brands if b["brand_id"] == args.brand_id] if args.brand_id else brands
    if not target:
        print(f"ERROR: brand-id '{args.brand_id}' not found.")
        sys.exit(1)

    total_brands = len(brands)
    print(f"Rendering PDFs for {len(target)} brand(s)...")

    errors = []
    for brand in target:
        brand_id = brand["brand_id"]
        print(f"  → {brand_id}...", end=" ", flush=True)
        try:
            pdf_path = render_brand_pdf(brand, args.year, args.month, total_brands)
            print(f"OK ({pdf_path.stat().st_size // 1024} KB)")
        except Exception as e:
            print(f"ERROR: {e}")
            errors.append(brand_id)

    print(f"\nPDFs: {len(target) - len(errors)}/{len(target)} rendered.")
    if errors:
        print(f"Failed: {', '.join(errors)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
