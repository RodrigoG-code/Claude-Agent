"""
render_sample.py
----------------
Renders a sample PDF report using the new template with full context structure.
Includes make_sparkline_svg() for daily trend charts.

Usage:
    .venv/bin/python tools/render_sample.py
"""

import base64
import json
import random
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "tools" / "templates"
CONFIG_DIR = BASE_DIR / "config"
OUTPUT_DIR = BASE_DIR / "outputs"


# ── Sparkline SVG generator ──────────────────────────────────────

def make_sparkline_svg(data, color='#BA7517', width=688, height=90):
    """Generate a pure SVG sparkline chart — no JS, fully WeasyPrint compatible.

    Args:
        data: list of floats (daily values)
        color: stroke/dot colour
        width: SVG width in px (688 = exact A4 content width at 96dpi)
        height: SVG height in px

    Returns:
        SVG string
    """
    if not data or len(data) < 2:
        return ''
    pad_left, pad_right, pad_top, pad_bottom = 8, 8, 4, 20
    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom
    min_v = min(data)
    max_v = max(data)
    rng = max_v - min_v if max_v != min_v else 1

    def x(i):
        return pad_left + (i / (len(data) - 1)) * chart_w

    def y(v):
        return pad_top + (1 - (v - min_v) / rng) * chart_h

    points = [(x(i), y(v)) for i, v in enumerate(data)]
    path_d = 'M ' + ' L '.join(f'{px:.1f},{py:.1f}' for px, py in points)

    grid_lines = ''
    for i in range(3):
        gy = pad_top + (i / 2) * chart_h
        grid_lines += f'<line x1="{pad_left}" y1="{gy:.1f}" x2="{width - pad_right}" y2="{gy:.1f}" stroke="#e8e8e8" stroke-width="0.5"/>'

    n = len(data)
    x_labels = ''
    for idx in [0, n // 4, n // 2, 3 * n // 4, n - 1]:
        lx = x(idx)
        x_labels += f'<text x="{lx:.1f}" y="{height - 4}" text-anchor="middle" font-size="8" fill="#bbb">{idx + 1}</text>'

    dots = ''
    for px, py in points:
        dots += f'<circle cx="{px:.1f}" cy="{py:.1f}" r="1.8" fill="{color}"/>'

    return f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:{height}px">{grid_lines}<path d="{path_d}" fill="none" stroke="{color}" stroke-width="1.5" stroke-linejoin="round"/>{dots}{x_labels}</svg>'


# ── Load logo as base64 ──────────────────────────────────────────

def load_logo_b64():
    logo_path = TEMPLATE_DIR / "assets" / "napps_logo.svg"
    with open(logo_path, "rb") as f:
        return f"data:image/svg+xml;base64,{base64.b64encode(f.read()).decode()}"


# ── Load font ─────────────────────────────────────────────────────

def get_font_face():
    font_path = (TEMPLATE_DIR / "assets" / "fonts" / "PlayfairDisplay-Bold.ttf").resolve()
    if font_path.exists():
        return f"@font-face {{ font-family: 'Playfair Display'; src: url('file://{font_path}'); font-weight: 700; font-style: normal; }}\n"
    return ""


# ── Generate fake daily data ──────────────────────────────────────

def fake_daily(base, volatility=0.05, days=28):
    """Generate fake daily data as list of floats."""
    data = []
    v = base
    for d in range(days):
        v += v * random.uniform(-volatility, volatility)
        data.append(round(v, 2))
    return data


# ── Build full sample context ─────────────────────────────────────

def build_modab_context():
    """Build the full context dict for ModaB sample report."""
    logo_b64 = load_logo_b64()

    # Daily data for sparklines (list of floats)
    cart_daily = fake_daily(74.2, 0.02)
    conv_daily = fake_daily(2.1, 0.04)

    brand = {
        "name": "ModaB",
        "sector_display": "Fashion & Apparel",
        "market": "BR",
        "currency_symbol": "R$",
    }

    metrics = [
        {"label": "Total Sales",           "display_value": "R$ 869.071",  "prev_value": "R$ 781.160",  "mom": "▲ 11.2%",  "mom_dir": "up",   "flag": "none"},
        {"label": "Conversion Rate",       "display_value": "2.10%",       "prev_value": "2.40%",       "mom": "▼ 12.5%",  "mom_dir": "down", "flag": "Average"},
        {"label": "AOV",                   "display_value": "R$ 416,74",   "prev_value": "R$ 379,02",   "mom": "▲ 9.9%",   "mom_dir": "up",   "flag": "Good"},
        {"label": "Add-to-Cart Rate",      "display_value": "5.80%",       "prev_value": "6.20%",       "mom": "▼ 6.5%",   "mom_dir": "down", "flag": "Average"},
        {"label": "Cart Abandonment",      "display_value": "74.20%",      "prev_value": "71.50%",      "mom": "▲ 3.8%",   "mom_dir": "down", "flag": "Poor"},
        {"label": "CLV",                   "display_value": "R$ 1.126",    "prev_value": "R$ 1.083",    "mom": "▲ 3.9%",   "mom_dir": "up",   "flag": "Average"},
        {"label": "Churn Rate",            "display_value": "32.50%",      "prev_value": "30.10%",      "mom": "▲ 8.0%",   "mom_dir": "down", "flag": "Average"},
        {"label": "Sessions",              "display_value": "89,400",      "prev_value": "82,100",      "mom": "▲ 8.9%",   "mom_dir": "up",   "flag": "Good"},
        {"label": "Refund Rate",           "display_value": "8.20%",       "prev_value": "7.50%",       "mom": "▲ 9.3%",   "mom_dir": "down", "flag": "Average"},
        {"label": "Repeat Purchase",       "display_value": "18.50%",      "prev_value": "19.80%",      "mom": "▼ 6.6%",   "mom_dir": "down", "flag": "Average"},
        {"label": "Total Orders",          "display_value": "2,085",       "prev_value": "2,062",       "mom": "▲ 1.1%",   "mom_dir": "up",   "flag": "Average"},
    ]

    priority_metrics = [
        {
            "name": "Cart Abandonment Rate",
            "value": "74.20%",
            "flag": "Poor",
            "mom": "3.8%",
            "mom_dir": "down",
            "mom_arrow": "▲",
            "peer_rank": 38,
            "sector_good": "65.0%",
            "sector_poor": "78.0%",
            "benchmark_good": "65.0%",
            "sector_avg": "~70%",
            "gap_to_good": "9.2 pts above",
            "narrative": "At 74.2%, cart abandonment is <span class='napps-feature'>9.2 points above the fashion sector Good threshold of 65%</span> and trending toward Poor with a 3.8% MoM worsening. Ranked #38/48. Activate <span class='napps-feature'>Cart Abandonment Notifications</span> for automated push recovery, configure the <span class='napps-feature'>Free Shipping Progress Bar</span> in Cart Customization, and integrate <span class='napps-feature'>Klaviyo</span> for multi-channel abandoned cart flows.",
            "daily_data": cart_daily,
            "daily_chart_svg": make_sparkline_svg(cart_daily, color="#E24B4A"),
        },
        {
            "name": "Conversion Rate",
            "value": "2.10%",
            "flag": "Average",
            "mom": "12.5%",
            "mom_dir": "down",
            "mom_arrow": "▼",
            "peer_rank": 18,
            "sector_good": "4.3%",
            "sector_poor": "1.0%",
            "benchmark_good": "4.3%",
            "sector_avg": "1.9%",
            "gap_to_good": "2.2 pts below",
            "narrative": "Conversion dropped 12.5% MoM from 2.40% to 2.10%, now 2.2 points below the Good threshold of 4.3%. The high-sessions-plus-low-conversion pattern signals UX friction. Activate <span class='napps-feature'>Quick Add to Cart</span> to reduce purchase steps, enable <span class='napps-feature'>NIA Product Recommendations</span> for AI-personalised suggestions, and deploy <span class='napps-feature'>Color Swatches</span> on listing pages.",
            "daily_data": conv_daily,
            "daily_chart_svg": make_sparkline_svg(conv_daily, color="#BA7517"),
        },
    ]

    secondary_metrics = [
        {"name": "AOV", "value": "R$ 416,74", "flag": "Good", "bar_pct": 55, "peer_rank": 8, "threshold_label": "≥R$ 730 Good", "mom": "9.9%", "mom_dir": "up", "mom_arrow": "▲", "narrative": "At the sector midpoint and trending up strongly. <span class='napps-feature'>Complete the Look</span> cross-sells can push toward the R$ 730 Good threshold."},
        {"name": "Add-to-Cart", "value": "5.80%", "flag": "Average", "bar_pct": 45, "peer_rank": 22, "threshold_label": "≥8% Good", "mom": "6.5%", "mom_dir": "down", "mom_arrow": "▼", "narrative": "Just above the fashion average of 5.4% but losing ground. <span class='napps-feature'>Shoppable Videos</span> capture intent at moment of inspiration."},
        {"name": "Repeat Purchase", "value": "18.5%", "flag": "Average", "bar_pct": 40, "peer_rank": 25, "threshold_label": "≥30% Good", "mom": "6.6%", "mom_dir": "down", "mom_arrow": "▼", "narrative": "Just 3.5 pts above Poor threshold and declining. <span class='napps-feature'>Loyalty Program Integration</span> with Growave creates structural switching costs."},
        {"name": "Sessions", "value": "89,400", "flag": "Good", "bar_pct": 85, "peer_rank": 6, "threshold_label": "peer rank", "mom": "8.9%", "mom_dir": "up", "mom_arrow": "▲", "narrative": "Top-quartile traffic. Priority is converting existing visitors — the #6 vs #18 gap is the biggest structural opportunity."},
        {"name": "Churn Rate", "value": "32.5%", "flag": "Average", "bar_pct": 65, "peer_rank": 35, "threshold_label": "≤55% Good", "mom": "8.0%", "mom_dir": "down", "mom_arrow": "▲", "narrative": "Well below the 55% Good threshold — a genuine strength. The 8% MoM worsening needs monitoring before it compounds."},
        {"name": "Refund Rate", "value": "8.20%", "flag": "Average", "bar_pct": 70, "peer_rank": 40, "threshold_label": "≤15% Good", "mom": "9.3%", "mom_dir": "down", "mom_arrow": "▲", "narrative": "Exceptionally strong for fashion (sector average 20–30%). Upward trend needs monitoring. <span class='napps-feature'>Kiwi Sizing</span> is the highest-impact preventive measure."},
    ]

    cover_metrics = [
        {"label": "Total Sales", "value": "R$ 869k", "mom": "▲ 11.2%", "mom_dir": "up", "flag": "good", "rank": "#5 / 48"},
        {"label": "Conversion", "value": "2.10%", "mom": "▼ 12.5%", "mom_dir": "down", "flag": "Average", "rank": "#18 / 48"},
        {"label": "Cart Abandon.", "value": "74.2%", "mom": "▲ 3.8%", "mom_dir": "down", "flag": "Poor", "rank": "#38 / 48"},
        {"label": "Repeat Purch.", "value": "18.5%", "mom": "▼ 6.6%", "mom_dir": "down", "flag": "Average", "rank": "#25 / 48"},
    ]

    recommendations = [
        {
            "title": "Deploy cart abandonment recovery system",
            "priority": "High",
            "feature": "Cart Abandonment Notifications · Klaviyo Integration · Free Shipping Progress Bar",
            "action": "Activate Cart Abandonment Notifications with triggers at 1h and 24h post-abandonment — push has 50% higher open rates than email. Layer into Klaviyo flows for multi-channel recovery. Configure the Free Shipping Progress Bar in Cart Customization. At 74.2% abandonment (#38/48), closing to the 65% Good threshold would yield ~800 additional orders monthly — a potential R$ 334.000+ revenue uplift.",
            "why": None,
            "effort": "Low · cart_abandonment_rate",
        },
        {
            "title": "Reverse conversion rate decline urgently",
            "priority": "High",
            "feature": "Quick Add to Cart · NIA Product Recommendations · Color Swatches",
            "action": "Activate Quick Add to Cart to reduce purchase steps. Enable NIA Product Recommendations on homepage and PDPs. Deploy Color Swatches on listing pages so fashion browsers can evaluate variants without clicking through each PDP. Conversion dropped 12.5% MoM while sessions grew 8.9%. The #6 vs #18 session-to-conversion gap means ModaB is paying to acquire visitors it fails to convert.",
            "why": None,
            "effort": "Low · conversion_rate",
        },
        {
            "title": "Arrest repeat purchase decline with loyalty",
            "priority": "High",
            "feature": "Loyalty Program Integration · App-Exclusive Discounts · Drops",
            "action": "Implement Loyalty Program Integration with Growave or Smile.io so customers earn points and build switching costs. Layer in App-Exclusive Discounts and Drops to create calendar-driven reasons to return. Set up Scheduled Notifications with post-purchase re-engagement flows. Repeat purchase fell to 18.5% — just 3.5 points above the Poor threshold, declining 6.6% MoM. Fashion average is 20–25%; ModaB is now below average.",
            "why": None,
            "effort": "Medium · repeat_purchase_rate, clv",
        },
        {
            "title": "Boost add-to-cart with shoppable content",
            "priority": "Medium",
            "feature": "Shoppable Videos · Complete the Look · Wishlist",
            "action": "Activate Shoppable Videos for a TikTok-style feed where customers purchase directly from content. Implement Complete the Look modules on PDPs to raise both add-to-cart and AOV simultaneously. Enable Wishlist with Wishlisted Discount Notifications. Add-to-cart declined 6.5% MoM to 5.8% and is losing ground against the 8% Good threshold.",
            "why": None,
            "effort": "Medium · add_to_cart_rate, aov",
        },
        {
            "title": "Monitor churn trend before it escalates",
            "priority": "Low",
            "feature": "Behavior Segmentation · Segmented Notifications",
            "action": "Set up Behavior Segmentation to identify at-risk customers early. Configure Segmented Notifications to target them with personalised win-back messages before they fully disengage. Churn at 32.5% is well below the 55% Good threshold — a genuine strength. However the 8% MoM worsening is a warning signal that requires monitoring.",
            "why": None,
            "effort": "Low · churn_rate",
        },
    ]

    return {
        "brand": brand,
        "report_month": "2026-02",
        "report_month_display": "February 2026",
        "overall_flag": "Average",
        "peer_rank_overall": 16,
        "total_brands": 48,
        "napps_logo_b64": logo_b64,
        "sessions_highlight": {
            "label": "Total Sales",
            "value": "R$ 869.071",
            "mom": "▲ 11.2% MoM",
            "rank": "#5 / 48",
        },
        "cover_headline": "Strong traffic growth but conversion falling — <strong>74.2% cart abandonment</strong>, 9.2 points above sector benchmark, is suppressing the revenue the traffic should be generating.",
        "cover_metrics": cover_metrics,
        "diagnostic_pattern": "ModaB ranks #6 in sessions but #18 in conversion — high traffic is failing to translate into orders. Combined with 74.2% cart abandonment (#38/48), this signals a clear UX and checkout friction problem that is actively suppressing revenue.",
        "executive_summary": "ModaB delivers an <strong>Average</strong> overall performance for February 2026, ranking <strong>#16 out of 48 brands</strong>. The standout positive is a <strong>strong 11.2% MoM increase in total sales</strong> driven by healthy traffic growth (#6 in sessions). However, conversion rate declined 12.5% MoM while sessions grew 8.9% — the funnel is becoming less efficient as traffic grows. Cart abandonment at 74.2% is the most critical metric, sitting 9.2 points above the fashion sector Good threshold of 65%.",
        "metrics": metrics,
        "priority_metrics": priority_metrics,
        "secondary_metrics": secondary_metrics,
        "recommendations": recommendations,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def render_pdf(context, output_name="modab_2026_02_report.pdf"):
    """Render the PDF from context dict."""
    css_text = (TEMPLATE_DIR / "report_styles.css").read_text(encoding="utf-8")
    font_face = get_font_face()
    context["styles"] = font_face + css_text

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    html_string = env.get_template("report_template.html").render(**context)

    # Save HTML for debugging
    html_path = BASE_DIR / ".tmp" / f"{output_name.replace('.pdf', '.html')}"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html_string, encoding="utf-8")

    # Render PDF
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = OUTPUT_DIR / output_name
    HTML(string=html_string, base_url=str(TEMPLATE_DIR)).write_pdf(str(pdf_path))
    print(f"PDF saved: {pdf_path} ({pdf_path.stat().st_size // 1024} KB)")
    return pdf_path


if __name__ == "__main__":
    random.seed(42)
    ctx = build_modab_context()
    render_pdf(ctx)
