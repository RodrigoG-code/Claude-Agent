"""
Scrape specific missing Napps pages using FireCrawl batch scrape.
"""

import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from firecrawl import FirecrawlApp

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

TMP = ROOT / ".tmp"
TMP.mkdir(exist_ok=True)

FIRECRAWL_KEY = os.getenv("FIRECRAWL_API_KEY")
if not FIRECRAWL_KEY:
    print("ERROR: FIRECRAWL_API_KEY not set in .env")
    sys.exit(1)

URLS = [
    "https://napps.io/homebuilder",
    "https://napps.io/productbuilder",
    "https://napps.io/builder",
    "https://napps.io/brand",
    "https://napps.io/automated",
    "https://napps.io/capabilities",
    "https://napps.io/integrations",
    "https://napps.io/faq",
    "https://napps.io/casestudy",
    "https://napps.io/pricing",
    "https://napps.io/notifications",
]

app = FirecrawlApp(api_key=FIRECRAWL_KEY)

all_pages = []
for i, url in enumerate(URLS):
    print(f"[{i+1}/{len(URLS)}] Scraping {url} ...")
    try:
        result = app.scrape(url, formats=["markdown"])
        md = result.markdown if hasattr(result, 'markdown') else result.get("markdown", "")
        meta = result.metadata if hasattr(result, 'metadata') else result.get("metadata", {})
        source_url = meta.get("sourceURL", url) if isinstance(meta, dict) else getattr(meta, 'sourceURL', url)
        all_pages.append({"url": source_url, "markdown": md})
        print(f"  OK ({len(md or '')} chars)")
    except Exception as e:
        print(f"  FAILED: {e}")
        all_pages.append({"url": url, "markdown": None, "error": str(e)})
    time.sleep(0.3)

raw_path = TMP / "napps_missing_raw.json"
with open(raw_path, "w", encoding="utf-8") as f:
    json.dump(all_pages, f, ensure_ascii=False, indent=2, default=str)

md_path = TMP / "napps_missing_markdown.txt"
with open(md_path, "w", encoding="utf-8") as f:
    for page in all_pages:
        f.write(f"\n{'='*80}\n")
        f.write(f"URL: {page['url']}\n")
        f.write(f"{'='*80}\n")
        f.write(page.get("markdown") or "(no content)")
        f.write("\n")

print(f"\nDone. {len(all_pages)} pages scraped.")
print(f"Markdown saved to {md_path}")
print(f"Raw data at {raw_path}")
