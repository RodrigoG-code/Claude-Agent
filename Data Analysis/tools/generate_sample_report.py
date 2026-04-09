"""
Generate a sample brand PDF report with mock data and Napps feature-based insights.
Step 1: Generate insights via Claude API using napps_feature_context.md
Step 2: Render HTML report using Jinja2
Step 3: Open HTML for review (can be printed to PDF from browser)
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

import anthropic
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "tools" / "templates"
CONFIG_DIR = BASE_DIR / "config"
TMP_DIR = BASE_DIR / ".tmp"

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

sys.path.insert(0, str(Path(__file__).resolve().parent))

# — Mock brand data ——————————————————————————————————————
SAMPLE_BRAND = {
    "brand_id": "modab-br",
    "brand_name": "ModaB",
    "sector": "fashion",
    "period": "2026-02",
    "data_complete": True,
    "cover_headline": "Strong traffic growth but conversion falling — <strong>74.2% cart abandonment</strong>, 9.2 points above sector benchmark, is suppressing the revenue the traffic should be generating.",
    "market": "PT",

    "total_sales": 142850.00,
    "sales_prev": 128400.00,
    "sales_mom_pct": 11.2,
    "peer_rank_sales": 5,

    "conversion_rate": 2.1,
    "conversion_rate_prev": 2.4,
    "conversion_rate_mom_pct": -12.5,
    "conversion_rate_flag": "Average",
    "peer_rank_conversion_rate": 18,

    "aov": 68.50,
    "aov_prev": 62.30,
    "aov_mom_pct": 9.9,
    "aov_flag": "Good",
    "peer_rank_aov": 8,

    "add_to_cart_rate": 5.8,
    "add_to_cart_rate_prev": 6.2,
    "add_to_cart_rate_mom_pct": -6.5,
    "add_to_cart_rate_flag": "Average",
    "peer_rank_add_to_cart_rate": 22,

    "cart_abandonment_rate": 74.2,
    "cart_abandonment_rate_prev": 71.5,
    "cart_abandonment_rate_mom_pct": 3.8,
    "cart_abandonment_rate_flag": "Poor",
    "peer_rank_cart_abandonment_rate": 38,

    "clv": 185.00,
    "clv_prev": 178.00,
    "clv_mom_pct": 3.9,
    "clv_flag": "Average",
    "peer_rank_clv": 15,

    "churn": 32.5,
    "churn_prev": 30.1,
    "churn_mom_pct": 8.0,
    "churn_flag": "Average",
    "peer_rank_churn": 35,

    "sessions": 89400,
    "sessions_prev": 82100,
    "sessions_mom_pct": 8.9,
    "sessions_flag": "Good",
    "peer_rank_sessions": 6,

    "refund_rate": 8.2,
    "refund_rate_prev": 7.5,
    "refund_rate_mom_pct": 9.3,
    "refund_rate_flag": "Average",
    "peer_rank_refund_rate": 40,

    "repeat_purchase_rate": 18.5,
    "repeat_purchase_rate_prev": 19.8,
    "repeat_purchase_rate_mom_pct": -6.6,
    "repeat_purchase_rate_flag": "Average",
    "peer_rank_repeat_purchase_rate": 25,

    "total_orders": 2085,
    "total_orders_prev": 2062,
    "total_orders_mom_pct": 1.1,
    "total_orders_flag": "Average",
    "peer_rank_total_orders": 12,

    "overall_flag": "Average",
    "overall_score": 1.15,
    "peer_rank_overall": 16,
}

TOTAL_BRANDS = 48

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

METRIC_LABELS = {
    "conversion_rate": "Conversion Rate",
    "aov": "Average Order Value (AOV)",
    "add_to_cart_rate": "Add-to-Cart Rate",
    "cart_abandonment_rate": "Cart Abandonment Rate",
    "clv": "Customer Lifetime Value (CLV)",
    "churn": "Churn Rate",
    "total_sales": "Total Sales",
    "sessions": "Sessions / Traffic",
    "refund_rate": "Refund / Return Rate",
    "repeat_purchase_rate": "Repeat Purchase Rate",
    "total_orders": "Number of Orders",
}


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

def fmt_value(metric, value):
    if value is None:
        return "N/A"
    if metric in {"conversion_rate", "add_to_cart_rate", "cart_abandonment_rate", "churn",
                   "refund_rate", "repeat_purchase_rate"}:
        return f"{value:.2f}%"
    if metric in {"aov", "clv", "total_sales"}:
        return f"€{value:,.2f}"
    if metric in {"sessions", "total_orders"}:
        return f"{int(value):,}"
    return str(value)

def fmt_mom_prompt(mom_pct):
    if mom_pct is None:
        return "no prior month data"
    direction = "▲" if mom_pct > 0 else ("▼" if mom_pct < 0 else "→")
    return f"{direction} {abs(mom_pct):.1f}% MoM"


def generate_insights(brand):
    """Generate insights using Claude with the Napps feature context."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    feature_context = (CONFIG_DIR / "napps_feature_context.md").read_text(encoding="utf-8")
    benchmarks_ref = (CONFIG_DIR / "benchmarks_reference.md").read_text(encoding="utf-8")
    system_prompt = feature_context + "\n\n---\n\n" + benchmarks_ref

    metrics_block = ""
    for metric, label in METRIC_LABELS.items():
        if metric == "total_sales":
            value_str = fmt_value(metric, brand.get("total_sales"))
            mom_str = fmt_mom_prompt(brand.get("sales_mom_pct"))
            metrics_block += f"- {label}: {value_str} ({mom_str})\n"
        else:
            value_str = fmt_value(metric, brand.get(metric))
            mom_str = fmt_mom_prompt(brand.get(f"{metric}_mom_pct"))
            flag = brand.get(f"{metric}_flag", "Unknown")
            emoji = FLAG_EMOJI.get(flag, "")
            metrics_block += f"- {label}: {value_str} ({mom_str}) → {emoji} {flag}\n"

    overall_flag = brand.get("overall_flag", "Unknown")
    peer_rank = brand.get("peer_rank_overall")
    peer_context = f"#{peer_rank} out of {TOTAL_BRANDS} brands" if peer_rank else "peer rank unavailable"

    prompt = f"""BRAND: {brand['brand_name']}
SECTOR: {brand['sector']}
PERIOD: {brand['period']}
OVERALL PERFORMANCE FLAG: {FLAG_EMOJI.get(overall_flag, '')} {overall_flag}
PEER RANKING: {peer_context}

METRICS:
{metrics_block}

Respond ONLY with valid JSON (no markdown, no explanation outside JSON) in this exact structure:
{{
  "executive_summary": "2-3 sentence high-level narrative. Mention the overall flag, the standout positive and the most critical concern.",
  "metric_narratives": {{
    "conversion_rate": "2-3 sentences interpreting this metric in context.",
    "aov": "2-3 sentences.",
    "add_to_cart_rate": "2-3 sentences.",
    "cart_abandonment_rate": "2-3 sentences.",
    "clv": "2-3 sentences.",
    "churn": "2-3 sentences.",
    "total_sales": "2-3 sentences on total sales trend.",
    "sessions": "2-3 sentences on traffic volume and trends.",
    "refund_rate": "2-3 sentences on returns and what they signal.",
    "repeat_purchase_rate": "2-3 sentences on customer loyalty.",
    "total_orders": "2-3 sentences on order volume in context."
  }},
  "top_improvements": [
    {{
      "title": "Short action title (5-8 words)",
      "priority": "High",
      "explanation": "3-4 sentences explaining what to do, why it matters, and the expected impact. MUST reference specific NAPPS features by name."
    }}
  ]
}}

Include 3-5 improvements. Priority must be one of: High, Medium, Low. Sort by priority descending.
Every recommendation MUST cite specific NAPPS features by name and explain the mechanism by which they move the metric.
Every metric narrative MUST reference the relevant sector benchmark explicitly — state the brand's value, the benchmark, and the delta in absolute terms."""

    client = anthropic.Anthropic(api_key=api_key)

    print("Calling Claude API for insights...")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = message.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    insights = json.loads(raw_text)
    print("Insights generated successfully.")
    return insights


def load_benchmarks(sector):
    """Load benchmarks from config/benchmarks.json for the given sector."""
    benchmarks_path = CONFIG_DIR / "benchmarks.json"
    with open(benchmarks_path) as f:
        all_benchmarks = json.load(f)
    # Try exact sector match, then fall back to default
    return all_benchmarks.get(sector, all_benchmarks.get("default", {}))


def load_napps_logo_b64():
    import base64
    logo_path = TEMPLATE_DIR / "assets" / "napps_logo.svg"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            return f"data:image/svg+xml;base64,{base64.b64encode(f.read()).decode()}"
    return ""


def build_cover_metrics(brand, napps_metrics):
    """Build the 4-item cover scorecard list."""
    cover_keys = ["conversion_rate", "cart_abandonment_rate", "repeat_purchase_rate"]
    metrics = []
    mom_val = brand.get("sales_mom_pct")
    metrics.append({
        "label": "Total Sales",
        "value": fmt_currency(brand.get("total_sales")),
        "mom": fmt_mom(mom_val),
        "mom_dir": "up" if mom_val and mom_val > 0 else "down",
        "flag": "Good",
        "rank": f"#{brand.get('peer_rank_sales', '—')}/{TOTAL_BRANDS}",
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
                "rank": f"#{m.get('peer_rank', '—')}/{TOTAL_BRANDS}",
            })
    return metrics


def build_context(brand, year, month):
    overall_flag = brand.get("overall_flag", "Unknown")

    # Load benchmarks from config file
    sector_benchmarks = load_benchmarks(brand.get("sector", "default"))

    napps_metrics = []
    for meta in NAPPS_METRIC_META:
        key = meta["key"]
        bm = sector_benchmarks.get(key, {})
        napps_metrics.append({
            **meta,
            "value": brand.get(key),
            "prev": brand.get(f"{key}_prev"),
            "mom_pct": brand.get(f"{key}_mom_pct"),
            "flag": brand.get(f"{key}_flag", "Unknown"),
            "peer_rank": brand.get(f"peer_rank_{key}"),
            "threshold_good": bm.get("good"),
            "threshold_poor": bm.get("poor"),
            "benchmark_good": bm.get("good"),
            "benchmark_poor": bm.get("poor"),
        })

    # Sessions highlight
    sessions = brand.get("sessions")
    sessions_highlight = None
    if sessions:
        sessions_highlight = {
            "label": "Sessions",
            "value": f"{int(sessions):,}",
            "mom": fmt_mom(brand.get("sessions_mom_pct")),
            "rank": f"#{brand.get('peer_rank_sessions', '—')}",
        }

    return {
        "brand_id": brand["brand_id"],
        "brand_name": brand["brand_name"],
        "sector": brand["sector"],
        "sector_display": SECTOR_DISPLAY.get(brand["sector"], brand["sector"].replace("_", " ").title()),
        "brand_market": brand.get("market", ""),
        "period": brand["period"],
        "period_label": f"{MONTH_NAMES[month]} {year}",
        "overall_flag": overall_flag,
        "flag_emoji": FLAG_EMOJI.get(overall_flag, ""),
        "total_sales": brand.get("total_sales"),
        "sales_prev": brand.get("sales_prev"),
        "sales_mom_pct": brand.get("sales_mom_pct"),
        "peer_rank_sales": brand.get("peer_rank_sales"),
        "peer_rank_overall": brand.get("peer_rank_overall"),
        "napps_logo_b64": load_napps_logo_b64(),
        "sessions_highlight": sessions_highlight,
        "cover_metrics": build_cover_metrics(brand, napps_metrics),
        "napps_metrics": napps_metrics,
        "insights": brand.get("insights", {}),
        "total_brands": TOTAL_BRANDS,
        "cover_headline": brand.get("cover_headline", ""),
        "data_warnings": [],
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def render_html(brand, year, month):
    """Render HTML report using Jinja2."""
    css_path = TEMPLATE_DIR / "report_styles.css"
    font_path = (TEMPLATE_DIR / "assets" / "fonts" / "PlayfairDisplay-Bold.ttf").resolve()
    font_face = f"""@font-face {{
    font-family: 'Playfair Display';
    src: url('file://{font_path}') format('truetype');
    font-weight: 700;
    font-style: normal;
}}
"""
    styles = font_face + css_path.read_text(encoding="utf-8")

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    env.filters.update({
        "fmt_currency": fmt_currency,
        "fmt_metric": fmt_metric,
        "fmt_mom": fmt_mom,
        "mom_class": mom_class,
        "fmt_rank": fmt_rank,
    })

    context = build_context(brand, year, month)
    context["styles"] = styles

    html_string = env.get_template("report_template.html").render(**context)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    output_path = TMP_DIR / f"{brand['brand_id']}_{year}_{month:02d}_sample.html"
    output_path.write_text(html_string, encoding="utf-8")
    return output_path


SAMPLE_INSIGHTS = {
    "executive_summary": "ModaB delivers an Average overall performance for February 2026, ranking #16 out of 48 brands. The standout positive is a strong 11.2% MoM increase in total sales driven by healthy traffic growth (#6 in sessions), but the most critical concern is a diagnostic pattern: high sessions combined with declining conversion and a Poor cart abandonment rate of 74.2% — 9.2 points above the fashion sector Good threshold of 65% — signalling a clear UX and checkout friction problem that is actively suppressing revenue.",
    "metric_narratives": {
        "conversion_rate": "At 2.10%, ModaB's conversion rate falls well below the fashion sector Good threshold of 4.3% (Littledata top 20%) and sits above the Poor threshold of 1.0%, with a concerning 12.5% MoM decline from 2.40%. The fashion sector average is 1.9%, so ModaB is slightly above average but 2.2 points below Good. Combined with strong sessions (#6), this creates a high-sessions-plus-low-conversion pattern — customers are arriving but not buying, making conversion optimisation the highest-ROI lever available.",
        "aov": "AOV of €68.50 falls between the fashion sector Poor threshold of €35 and Good threshold of €120 (Littledata), trending positively with a strong 9.9% MoM improvement from €62.30. The fashion average is €60–80, so ModaB sits right at the sector midpoint. Ranked #8 among peers, this is one of ModaB's strongest metrics. NAPPS's Free Shipping Progress Bar and Complete the Look cross-sell modules can push baskets toward the €120 Good threshold.",
        "add_to_cart_rate": "The add-to-cart rate of 5.80% sits between the fashion sector Poor threshold of 3.0% and Good threshold of 8.0% (Littledata top 20%), but is trending downward with a 6.5% MoM decline from 6.20%. The fashion average is 5.4%, so ModaB is just above average. At rank #22 out of 48 brands, ModaB is losing ground. NAPPS's Shoppable Videos and Quick Add to Cart would directly reduce the friction between browsing and intent expression.",
        "cart_abandonment_rate": "At 74.2%, cart abandonment is 9.2 points above the fashion sector Good threshold of 65% and approaching the Poor threshold of 78%. The fashion average is ~70%, putting ModaB 4.2 points worse than typical. Ranked #38 out of 48 brands, this is ModaB's worst peer ranking. The diagnostic pattern of high add-to-cart plus high abandonment signals checkout friction or price sensitivity. NAPPS's Cart Abandonment Notifications and Free Shipping Progress Bar are the highest-impact immediate fixes.",
        "clv": "CLV of €185.00 falls within the fashion sector Average range, sitting €65 below the Good threshold of €250. The 3.9% MoM improvement is positive but slow, ranking #15 among peers. To accelerate toward Good, ModaB needs to address both AOV (pushing toward €120) and repeat purchase rate simultaneously — NAPPS's Loyalty Program Integration with Growave combined with the Points System creates the structural incentive for both higher-value and more frequent orders.",
        "churn": "Churn at 32.5% is well below the fashion sector Good threshold of 55% and far below the Poor threshold of 70% — this is actually a strong metric by sector standards. However, the 8.0% MoM worsening from 30.1% is the real concern — this acceleration rate, if sustained, would erode this advantage. Automated win-back flows via NAPPS's Klaviyo Integration, combined with Segmented Notifications targeting customers showing declining engagement (via Behavior Segmentation), should arrest this trend before it compounds.",
        "total_sales": "Total sales of €142,850 show strong momentum with 11.2% MoM growth, ranking an impressive #5 out of 48 brands and well above the fashion Good threshold of €100,000. This growth is primarily traffic-driven rather than conversion-driven, which means significant headroom exists. If ModaB's 74.2% cart abandonment dropped to the sector Good benchmark of 65%, approximately 800 additional carts would convert monthly, potentially adding €55,000+ in revenue based on current AOV.",
        "sessions": "Sessions of 89,400 rank #6 among 48 peers with 8.9% MoM growth — a clear strength. Sessions are primarily benchmarked by peer rank, and this top-quartile position confirms ModaB's traffic acquisition is working well. The priority is not more traffic but better conversion of existing traffic: the gap between session rank (#6) and conversion rank (#18) is the brand's single biggest structural opportunity. NAPPS's Deep Links for Sharing and Smart App Banner can continue growing this channel while conversion work multiplies the value of every visit.",
        "refund_rate": "The refund rate of 8.20% is well below the fashion sector Good threshold of 15% (fashion average is 20–30%), making this one of ModaB's strongest metrics by sector standards. However, the 9.3% MoM worsening from 7.50% needs monitoring. For fashion, 8.2% is exceptionally strong — the typical fashion return rate is 20–30%. NAPPS's Kiwi Sizing integration remains the highest-impact preventive measure, while Product Stories showing products in real-life context can reduce expectation gaps.",
        "repeat_purchase_rate": "Repeat purchase rate of 18.50% sits between the fashion sector Poor threshold of 15% and Good threshold of 30% (Opensend/MobiLoud), with a concerning 6.6% MoM decline from 19.80%. The fashion average is 20–25%, putting ModaB slightly below average. Ranked #25, ModaB is in the bottom half. NAPPS's App-Exclusive Discounts and Drops create immediate reasons to return, while Loyalty Program Integration with Growave builds the structural retention system needed to close the 11.5-point gap to Good.",
        "total_orders": "Total orders of 2,085 are benchmarked by peer rank, sitting at #12 out of 48 — solid upper-quartile positioning and above the fashion Good threshold of 500 orders. However, the 1.1% MoM growth despite 8.9% traffic growth reveals a widening efficiency gap: traffic is growing 8x faster than orders. Fixing cart abandonment from 74.2% to the sector Good benchmark of 65% could yield approximately 800 additional monthly orders — without any increase in acquisition spend."
    },
    "top_improvements": [
        {
            "title": "Deploy Cart Abandonment Recovery System",
            "priority": "High",
            "explanation": "With 74.2% cart abandonment (ranked #38/48, flagged Poor), this is ModaB's most critical issue — 9.2 points above the fashion sector Good threshold of 65%. Activate NAPPS's Cart Abandonment Notifications to automatically push-notify customers who leave items in cart — push has 50% higher open rates than email and 40% of users engage within the first hour. Complement this with the Klaviyo Integration to layer push into existing email abandonment flows for multi-channel recovery. Configure the Free Shipping Progress Bar in NAPPS's Cart Customization to show customers how close they are to free shipping, which directly reduces abandonment by motivating completion. If ModaB reduced abandonment to the sector Good threshold of 65%, approximately 800 additional carts would convert monthly — a potential €55,000+ revenue uplift."
        },
        {
            "title": "Reverse Conversion Rate Decline Urgently",
            "priority": "High",
            "explanation": "Conversion rate dropped 12.5% MoM from 2.40% to 2.10%, ranked #18/48. While above the fashion Poor threshold of 1.0%, ModaB is 2.2 points below the Good threshold of 4.3% (Littledata top 20%) and the gap is widening. The high-sessions-plus-low-conversion pattern — #6 in traffic but #18 in conversion — means ModaB is paying to acquire visitors it fails to convert. Activate NAPPS's Quick Add to Cart so customers can add items directly from collection views without extra clicks. Enable NIA Product Recommendations to surface AI-personalised suggestions on homepage and product pages. Deploy Color Swatches on listing pages so fashion browsers can evaluate variants without clicking through to each PDP."
        },
        {
            "title": "Arrest Repeat Purchase Rate Decline with Loyalty",
            "priority": "High",
            "explanation": "Repeat purchase rate fell 6.6% MoM to 18.50%, ranked #25/48 — just 3.5 points above the fashion Poor threshold of 15% and 11.5 points below Good at 30%. The fashion average is 20–25%, so ModaB is now below average and trending in the wrong direction. Implement NAPPS's Loyalty Program Integration with Growave or Smile.io so customers earn points on every purchase and unlock VIP tiers — unredeemed point balances create a tangible switching cost. Layer in App-Exclusive Discounts and Drops to create immediate, calendar-driven reasons for customers to return. Set up Scheduled Notifications with post-purchase re-engagement flows at optimal intervals."
        },
        {
            "title": "Boost Add-to-Cart with Shoppable Content",
            "priority": "Medium",
            "explanation": "Add-to-cart rate declined 6.5% MoM to 5.80%, ranked #22/48. The fashion sector Good threshold is 8.0% (Littledata top 20%), putting ModaB 2.2 points below — and the gap is growing. Activate NAPPS's Shoppable Videos to create a TikTok-style content feed where customers can purchase directly from video content, capturing intent at the moment of inspiration. For fashion specifically, implement Complete the Look cross-sell modules on PDPs to show complementary items, which increases both add-to-cart rate and AOV simultaneously. Enable Wishlist with Wishlisted Discount Notifications to convert saved intent into future add-to-cart actions."
        },
        {
            "title": "Monitor Churn Trend Before It Escalates",
            "priority": "Low",
            "explanation": "Churn at 32.5% is well below the fashion sector Good threshold of 55% — a strong metric by sector standards. However, the 8.0% MoM worsening from 30.1% is a warning signal that needs monitoring. Set up NAPPS's Behavior Segmentation to identify at-risk customers based on declining engagement signals before they fully churn. Configure Segmented Notifications to automatically target customers showing early churn indicators with personalised win-back messages. No immediate structural intervention needed, but if the trend continues for another month, escalate to a Loyalty Program Integration to create formal switching costs."
        }
    ]
}


if __name__ == "__main__":
    brand = SAMPLE_BRAND.copy()

    # Try Claude API, fall back to sample insights
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            brand["insights"] = generate_insights(brand)
        except Exception as e:
            print(f"API call failed ({e}), using sample insights...")
            brand["insights"] = SAMPLE_INSIGHTS
    else:
        print("No API key, using sample insights...")
        brand["insights"] = SAMPLE_INSIGHTS

    # Save data
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    with open(TMP_DIR / "sample_brand_data.json", "w") as f:
        json.dump(brand, f, indent=2)

    # Render HTML
    print("Rendering HTML report...")
    html_path = render_html(brand, 2026, 2)
    print(f"\nDone! HTML saved to: {html_path}")
