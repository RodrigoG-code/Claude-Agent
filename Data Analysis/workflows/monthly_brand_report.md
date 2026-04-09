# Workflow: Monthly Brand Performance Report

## Objective
Generate monthly performance reports for all active Napps brands (~50), flagging each as Good / Average / Poor across 11 ecommerce metrics. Outputs: one PDF per brand + one Excel workbook, uploaded to Google Drive, with the historical snapshot stored in Google Sheets.

## Schedule
Runs on the **2nd of each month at 08:00** (the 2nd gives the Napps API time to finalise the previous month's data). Use `trigger_monthly_report.py` as the entry point.

To schedule on macOS:
1. Create `~/Library/LaunchAgents/com.napps.monthly-report.plist` with:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.napps.monthly-report</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/nunobatista/Desktop/Data Analysis/.venv/bin/python</string>
        <string>/Users/nunobatista/Desktop/Data Analysis/tools/trigger_monthly_report.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Day</key>  <integer>2</integer>
        <key>Hour</key> <integer>8</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/nunobatista/Desktop/Data Analysis/.tmp/launchd_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/nunobatista/Desktop/Data Analysis/.tmp/launchd_stderr.log</string>
</dict>
</plist>
```
2. Load it: `launchctl load ~/Library/LaunchAgents/com.napps.monthly-report.plist`

---

## Required Inputs
- `.env` — all API credentials (see below)
- `credentials.json` — Google Service Account credentials (gitignored)
- Google Sheets — `brand_config`, `benchmark_config`, `monthly_snapshots` sheets

## Required .env Keys
```
ANTHROPIC_API_KEY
NAPPS_CLIENT_ID_{BRAND_SLUG}     (one per brand)
NAPPS_CLIENT_SECRET_{BRAND_SLUG} (one per brand)
```

---

## Pipeline Steps

### Step 0 — Refresh Napps Feature Catalog (Automated)
```bash
python tools/refresh_napps_features.py
```
- **Runs automatically as the first step of the pipeline** (non-blocking — pipeline continues even if refresh fails)
- Re-crawls napps.io (main site + feature pages) via FireCrawl
- Uses Claude to compare scraped content against existing `config/napps_feature_context.md`
- If new features detected: auto-updates both `config/napps_features.xlsx` and `config/napps_feature_context.md`
- New features are added to a "NEW FEATURES (Auto-detected)" section in the context file — review and move to appropriate metric sections when convenient
- Refresh log saved to `.tmp/feature_refresh_log.json`
- **Requires:** `FIRECRAWL_API_KEY` and `ANTHROPIC_API_KEY` in `.env`

### Step 1 — Fetch Napps
```bash
python tools/fetch_napps.py --year YYYY --month MM
```
- Pulls all 11 metrics from Napps REST API: total_sales, conversion_rate, AOV, add_to_cart_rate, cart_abandonment_rate, CLV, churn, sessions, refund_rate, repeat_purchase_rate, total_orders
- Output: `.tmp/raw/napps/{brand_id}_YYYY_MM.json`
- **⚠️ First-time setup:** Verify Napps API endpoints in `fetch_napps.py` against docs. Look for:
  - `NAPPS_AUTH_URL` — the OAuth2 token endpoint
  - `NAPPS_API_BASE` — base URL
  - `NAPPS_METRICS_ENDPOINT` — analytics path
  - `FIELD_MAP` — mapping from Napps JSON field names to our internal names
- Update `fetch_napps.py` and re-run if any field is `null` in the output JSON
- **After confirming endpoints:** Delete this note and document the confirmed URLs here

### Step 2 — Process
```bash
python tools/merge_metrics.py --year YYYY --month MM
```
- Processes Napps raw files into a unified snapshot per brand
- Loads prior month snapshot to compute MoM deltas
- Output: `.tmp/processed/metrics_YYYY_MM.json`
- **Check:** Review any warnings about brands with incomplete data before proceeding

### Step 3 — Score
```bash
python tools/score_brands.py --year YYYY --month MM
```
- Evaluates each metric using 4 signals: sector threshold, universal benchmark, MoM trend, peer rank
- Assigns per-metric flags + overall brand flag (Good/Average/Poor)
- Output: `.tmp/processed/peer_ranks_YYYY_MM.json`
- **Check:** Review the Good/Average/Poor distribution printed at the end. If it looks wrong (e.g. all brands are Poor on first run), verify:
  - `brand_config` sheet has threshold values filled in
  - `benchmark_config` sheet has entries for your sectors and metrics
  - Metric value ranges from Napps match what the thresholds expect

### Step 4 — Generate Insights
```bash
python tools/generate_insights.py --year YYYY --month MM
```
- Calls Claude API (claude-sonnet-4-6) for each brand: ~50 API calls
- **Before first run:** Confirm Anthropic API credit balance
- Output: adds `insights` key to each brand record in `peer_ranks_YYYY_MM.json`
- **If quality is low:** Review the prompt in `generate_insights.py` → `build_prompt()`. Adjust sector context, metric framing, or instruction clarity. Test with `--brand-id` on one brand before re-running all 50.
- **Rate limits:** If you hit rate limits, add a small `time.sleep(0.5)` between calls in the loop

### Step 5 — Render PDFs
```bash
python tools/render_pdf.py --year YYYY --month MM
```
- Generates A4 PDF per brand using WeasyPrint + Jinja2 template
- Output: `.tmp/reports/pdf/{brand_id}_YYYY_MM.pdf`
- **Check:** Open 2-3 PDFs and verify layout, page breaks, flag badge colours, and that insights text appears
- **Template customisation:** Edit `tools/templates/report_template.html` and `report_styles.css` to change branding (logo, colours, fonts). The Napps purple is `#6d28d9` in the CSS.
- **WeasyPrint issues:** If fonts render incorrectly on macOS, install system fonts or use web-safe fonts. Avoid Google Fonts (requires internet during render).

### Step 6 — Render Excel
```bash
python tools/render_excel.py --year YYYY --month MM
```
- Generates one Excel workbook with 3 sheets: Overview, Recommendations, Raw Data
- Output: `.tmp/reports/excel/brand_performance_YYYY_MM.xlsx`
- **Check:** Open and verify colour-coded flag cells, auto-filter, frozen header row

### Step 7 — Save Snapshot
```bash
python tools/save_snapshot.py --year YYYY --month MM
```
- Saves historical snapshot locally for MoM tracking

### Step 8 — Organise Reports
```bash
python tools/organize_reports.py --year YYYY --month MM
```
- Moves reports to `outputs/YYYY_MM/`

---

## Running the Full Pipeline
```bash
# Default: runs for previous month
python tools/trigger_monthly_report.py

# Specific month:
python tools/trigger_monthly_report.py --year 2026 --month 2

# Single brand (for testing):
python tools/trigger_monthly_report.py --year 2026 --month 3 --brand-id acme-uk

# Resume from step 3 (if steps 1-2 already ran):
python tools/trigger_monthly_report.py --year 2026 --month 3 --skip-steps 1,2
```

Run log is written to `.tmp/run_log.txt`.

---

## Adding a New Brand
1. Add to `.env`:
   ```
   NAPPS_CLIENT_ID_{BRAND_SLUG}=...
   NAPPS_CLIENT_SECRET_{BRAND_SLUG}=...
   ```
2. Add the brand to `config/brands.json`:
   - Fill in `brand_id` (use the same slug as in env var names), `brand_name`, `sector`
   - Fill in `napps_client_id_key`, `napps_client_secret_key` with the env var names
   - Fill in threshold values for the brand's sector (copy from another brand in the same sector as a starting point)
   - Set `active: true`
3. Next monthly run will automatically include the new brand

---

## Google Sheets Structure

### `config/brands.json` — required fields per brand
| Field | Description |
|---|---|
| `brand_id` | Unique slug, no spaces (e.g. `acme-uk`) |
| `brand_name` | Display name |
| `sector` | e.g. `fashion`, `beauty`, `electronics` |
| `napps_client_id_key` | Name of env var, e.g. `NAPPS_CLIENT_ID_ACME_UK` |
| `napps_client_secret_key` | Name of env var, e.g. `NAPPS_CLIENT_SECRET_ACME_UK` |
| `thresholds` | Object with per-metric `{good, poor}` values |
| `active` | `true` or `false` |

Threshold metrics: `total_sales`, `conversion_rate`, `aov`, `add_to_cart_rate`, `cart_abandonment_rate`, `clv`, `churn`, `sessions`, `refund_rate`, `repeat_purchase_rate`, `total_orders`.

### `config/benchmarks.json` — structure
Keyed by sector, then by metric. Each metric has `good`, `poor`, and optional `source` fields.

---

## Scoring Algorithm Reference

### Per-metric score
```
threshold_score (0/1/2) × 0.35  ← brand-specific sector threshold
benchmark_score (0/1/2) × 0.35  ← universal industry benchmark
trend_score (-0.5/0/+0.5) × 0.15  ← MoM direction
peer_score  (-0.5/0/+0.5) × 0.15  ← top/middle/bottom third peer rank
```
Missing signals are excluded and weights are renormalised.

### Metric flag
- score ≥ 1.5 → **Good**
- score ≥ 0.8 → **Average**
- score < 0.8 → **Poor**

### Overall brand score weights
| Metric | Weight |
|---|---|
| Conversion rate | 0.20 |
| Total sales | 0.15 |
| CLV | 0.15 |
| Cart abandonment rate | 0.10 |
| AOV | 0.08 |
| Sessions / Traffic | 0.07 |
| Churn | 0.05 |
| Add-to-cart rate | 0.05 |
| Refund / Return rate | 0.05 |
| Repeat purchase rate | 0.05 |
| Number of orders | 0.05 |

### Lower-is-better metrics
Cart abandonment rate, churn, and refund rate are inverted: a decrease is an improvement.

---

## Known Issues / Lessons Learned
*(Update this section as you discover quirks during real runs)*

- **First run (no prior month data):** MoM deltas will all be `null`. The scoring algorithm handles this gracefully by excluding the trend signal and renormalising weights. Historical data accumulates from the second run onwards.
- **Napps API endpoints:** Need to be confirmed from Napps documentation before first run. See `fetch_napps.py` TODO comments.
- **WeasyPrint on macOS:** Install with `pip install weasyprint`. May require `brew install pango` for proper font rendering.
- **Google Service Account:** Must be granted editor access to the Google Sheets spreadsheet and editor access to the Google Drive folder.
