"""
generate_insights.py
--------------------
Calls the Claude API (claude-sonnet-4-6) for each brand to generate:
  - executive_summary: 2-3 sentence narrative overview
  - metric_narratives: per-metric interpretation (2-3 sentences each)
  - top_improvements: list of 3-5 prioritised recommendations

Usage:
    python tools/generate_insights.py --year 2026 --month 3
    python tools/generate_insights.py --year 2026 --month 3 --brand-id acme-uk

Inputs:
    .tmp/processed/peer_ranks_YYYY_MM.json

Outputs:
    .tmp/processed/peer_ranks_YYYY_MM.json (updated in-place with insights added)
"""

import argparse
import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / ".tmp" / "processed"

ANTHROPIC_MODEL = "claude-sonnet-4-6"

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

FLAG_EMOJI = {"Good": "✅", "Average": "⚠️", "Poor": "❌", "Unknown": "❓"}


def fmt_value(metric: str, value) -> str:
    """Format a metric value for display in the prompt."""
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


def fmt_mom(mom_pct) -> str:
    if mom_pct is None:
        return "no prior month data"
    direction = "▲" if mom_pct > 0 else ("▼" if mom_pct < 0 else "→")
    return f"{direction} {abs(mom_pct):.1f}% MoM"


def build_prompt(brand: dict, total_brands: int) -> str:
    brand_id = brand["brand_id"]
    brand_name = brand.get("brand_name", brand_id)
    sector = brand.get("sector", "ecommerce")
    period = brand.get("period", "")
    overall_flag = brand.get("overall_flag", "Unknown")
    peer_rank = brand.get("peer_rank_overall")
    peer_context = f"#{peer_rank} out of {total_brands} brands" if peer_rank else "peer rank unavailable"

    metrics_block = ""
    for metric, label in METRIC_LABELS.items():
        if metric == "total_sales":
            value_str = fmt_value(metric, brand.get("total_sales"))
            mom_str = fmt_mom(brand.get("sales_mom_pct"))
            metrics_block += f"- {label}: {value_str} ({mom_str})\n"
        else:
            value_str = fmt_value(metric, brand.get(metric))
            mom_str = fmt_mom(brand.get(f"{metric}_mom_pct"))
            flag = brand.get(f"{metric}_flag", "Unknown")
            emoji = FLAG_EMOJI.get(flag, "")
            metrics_block += f"- {label}: {value_str} ({mom_str}) — {emoji} {flag}\n"

    prompt = f"""You are a senior ecommerce performance analyst at Napps, an app platform that powers mobile shopping experiences.

BRAND: {brand_name}
SECTOR: {sector}
PERIOD: {period}
OVERALL PERFORMANCE FLAG: {FLAG_EMOJI.get(overall_flag, '')} {overall_flag}
PEER RANKING: {peer_context}

METRICS:
{metrics_block}
CONTEXT:
- All data comes from the Napps platform (total sales, conversion rate, AOV, add-to-cart, cart abandonment, CLV, churn, sessions, refund rate, repeat purchase rate, total orders)
- Performance flags are based on sector-specific thresholds, industry benchmarks, MoM trends, and peer comparisons

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
      "explanation": "3-4 sentences explaining what to do, why it matters, and the expected impact."
    }}
  ]
}}

Include 3-5 improvements. Priority must be one of: High, Medium, Low. Sort by priority descending.
Focus on practical, specific actions relevant to mobile ecommerce for the {sector} sector."""

    return prompt


def generate_brand_insights(client: anthropic.Anthropic, brand: dict, total_brands: int) -> dict:
    prompt = build_prompt(brand, total_brands)

    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = message.content[0].text.strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    insights = json.loads(raw_text)
    return insights


def main():
    parser = argparse.ArgumentParser(description="Generate AI insights per brand via Claude API.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--brand-id", type=str, default=None)
    args = parser.parse_args()

    input_path = PROCESSED_DIR / f"peer_ranks_{args.year}_{args.month:02d}.json"
    if not input_path.exists():
        print(f"ERROR: {input_path} not found. Run score_brands.py first.")
        sys.exit(1)

    with open(input_path) as f:
        brands = json.load(f)

    if args.brand_id:
        target_brands = [b for b in brands if b["brand_id"] == args.brand_id]
        if not target_brands:
            print(f"ERROR: brand-id '{args.brand_id}' not found in scored data.")
            sys.exit(1)
    else:
        target_brands = brands

    total_brands = len(brands)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print(f"Generating insights for {len(target_brands)} brand(s) using {ANTHROPIC_MODEL}...")
    errors = []

    # Build a lookup map so we can update brands in-place
    brands_by_id = {b["brand_id"]: b for b in brands}

    for brand in target_brands:
        brand_id = brand["brand_id"]
        print(f"  → {brand_id}...", end=" ", flush=True)
        try:
            insights = generate_brand_insights(client, brand, total_brands)
            brands_by_id[brand_id]["insights"] = insights
            print(f"OK ({brand.get('overall_flag', '?')})")
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            errors.append(brand_id)
            brands_by_id[brand_id]["insights"] = {"error": f"JSON parse failed: {e}"}
        except Exception as e:
            print(f"ERROR: {e}")
            errors.append(brand_id)
            brands_by_id[brand_id]["insights"] = {"error": str(e)}

    # Write updated data back to the same file
    with open(input_path, "w") as f:
        json.dump(list(brands_by_id.values()), f, indent=2)

    print(f"\nInsights generated: {len(target_brands) - len(errors)}/{len(target_brands)}")
    if errors:
        print(f"Failed: {', '.join(errors)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
