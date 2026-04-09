"""
trigger_monthly_report.py
--------------------------
Orchestrates the full monthly brand performance report pipeline.
Runs all steps in sequence, surfaces errors at each stage, and
prints a final summary on completion.

Usage:
    # Run for previous month (default, used by scheduler)
    .venv/bin/python tools/trigger_monthly_report.py

    # Run for a specific month (backfills or reruns)
    .venv/bin/python tools/trigger_monthly_report.py --year 2026 --month 2

    # Run for a single brand only (useful for testing)
    .venv/bin/python tools/trigger_monthly_report.py --year 2026 --month 3 --brand-id acme-uk

    # Skip specific steps (useful when resuming a partial run)
    .venv/bin/python tools/trigger_monthly_report.py --year 2026 --month 3 --skip-steps 1,2,3

Scheduling (macOS launchd):
    See workflows/monthly_brand_report.md for plist setup instructions.
    Runs on the 2nd of each month at 08:00 to allow APIs to finalise prior month data.
"""

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = BASE_DIR / ".tmp" / "run_log.txt"

# (step_number, script, label, supports_brand_filter)
STEPS = [
    (0, "refresh_napps_features.py", "Refresh Napps feature catalog", False),
    (1, "fetch_napps.py",        "Fetch Napps data",              True),
    (2, "merge_metrics.py",      "Process + compute MoM deltas",  False),
    (3, "score_brands.py",       "Score and flag brands",         False),
    (4, "generate_insights.py",  "Generate Claude insights",      False),
    (5, "render_pdf.py",         "Render PDFs",                   True),
    (6, "render_excel.py",       "Render Excel",                  False),
    (7, "save_snapshot.py",      "Save historical snapshot",      False),
    (8, "organize_reports.py",   "Organise reports to outputs/",  False),
]


def log(msg: str):
    print(msg)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")


def run_step(step_num, script, year, month, brand_id, supports_filter):
    cmd = [sys.executable, str(BASE_DIR / "tools" / script)]
    # Step 0 (feature refresh) takes no year/month args
    if step_num > 0:
        cmd += ["--year", str(year), "--month", str(month)]
        if brand_id and supports_filter:
            cmd += ["--brand-id", brand_id]
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def prev_month_from_today():
    today = date.today()
    return (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)


def main():
    parser = argparse.ArgumentParser(description="Run the full monthly brand performance pipeline.")
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--month", type=int, default=None)
    parser.add_argument("--brand-id", type=str, default=None)
    parser.add_argument("--skip-steps", type=str, default="")
    args = parser.parse_args()

    year, month = (args.year, args.month) if (args.year and args.month) else prev_month_from_today()
    skip_steps = {int(s.strip()) for s in args.skip_steps.split(",") if s.strip().isdigit()}

    period = f"{year}-{month:02d}"
    log(f"\n{'='*60}")
    log(f"Napps Monthly Report Pipeline — {period}")
    if args.brand_id:
        log(f"Brand filter: {args.brand_id}")
    if skip_steps:
        log(f"Skipping steps: {sorted(skip_steps)}")
    log(f"{'='*60}")

    failed_steps = []

    for step_num, script, label, supports_filter in STEPS:
        if step_num in skip_steps:
            log(f"  [{step_num}/{len(STEPS)}] SKIPPED — {label}")
            continue

        log(f"\n[{step_num}/{len(STEPS)}] {label}...")
        success = run_step(step_num, script, year, month, args.brand_id, supports_filter)

        if success:
            log(f"  ✓ Done")
        else:
            log(f"  ✗ FAILED — {script}")
            failed_steps.append((step_num, label))

            # Steps 1–4 are blocking (Step 0 is non-blocking)
            if 1 <= step_num <= 4:
                resume = ",".join(str(s) for s in range(1, step_num))
                log(f"\nAborted at step {step_num}. Fix the error and resume with:")
                log(f"  --skip-steps {resume}" if resume else "  (re-run without --skip-steps)")
                sys.exit(1)
            else:
                log(f"  Non-blocking — continuing...")

    log(f"\n{'='*60}")
    if not failed_steps:
        log(f"Pipeline complete ✓ — Period: {period}")
        log(f"Reports: outputs/{year}_{month:02d}/")
    else:
        log(f"Finished with {len(failed_steps)} warning(s):")
        for step_num, label in failed_steps:
            log(f"  ! Step {step_num}: {label}")
    log(f"{'='*60}\n")

    if failed_steps:
        sys.exit(1)


if __name__ == "__main__":
    main()
