# facebook_scraper_pro.py
#
# Facebook Scraper Pro – Phase 1 (Final Updated Version)
#
# Modules required in same folder:
#   - core_extractor.py
#   - facebook_adapter.py
#   - html_reporter.py
#   - utils.py
#
# Requirements:
#   pip install playwright bs4
#   playwright install chromium
#
# Launch Chromium:
#   chromium --remote-debugging-port=9222

import asyncio
from datetime import datetime
import os
from playwright.async_api import async_playwright

from core_extractor import extract_raw_blocks
from facebook_adapter import adapt_facebook_blocks
from html_reporter import generate_html_report
from utils import slugify_url


async def main():
    print("\n=== FACEBOOK SCRAPER PRO ===\n")

    # --------------------------------
    # User Inputs
    # --------------------------------
    filter_text = input("Filter by text (blank = any): ").strip().lower()

    auto_s = input("Auto-scroll? (y/N): ").strip().lower()
    do_scroll = (auto_s == "y")

    scroll_steps_raw = input("Scroll steps (default 10): ").strip()
    scroll_steps = int(scroll_steps_raw) if scroll_steps_raw.isdigit() else 10

    # --------------------------------
    # Connect to Chromium
    # --------------------------------
    print("\nConnecting to Chromium on port 9222...")
    print("If Chromium is not running, start it with:")
    print("  chromium --remote-debugging-port=9222\n")

    playwright = await async_playwright().start()

    try:
        browser = await playwright.chromium.connect_over_cdp("http://localhost:9222")
    except Exception as e:
        print("❌ Could not connect to Chromium.")
        print("Start it with:")
        print("  chromium --remote-debugging-port=9222")
        print("\nDetails:", e)
        return

    if not browser.contexts:
        print("No active contexts found in Chromium.")
        return

    ctx = browser.contexts[0]
    page = ctx.pages[0]
    page_url = page.url

    print(f"Attached to page: {page_url}\n")

    # --------------------------------
    # Auto Scroll
    # --------------------------------
    if do_scroll:
        print(f"Scrolling {scroll_steps} steps...\n")
        for i in range(scroll_steps):
            await page.evaluate("window.scrollBy(0,1500);")
            await asyncio.sleep(1.5)

    # --------------------------------
    # Extract DOM blocks
    # --------------------------------
    print("Extracting raw DOM blocks...")
    raw_blocks = await extract_raw_blocks(page)
    print(f"Found {len(raw_blocks)} raw blocks.")

    if filter_text:
        raw_blocks = [
            b for b in raw_blocks
            if filter_text in (b.get("text") or "").lower()
        ]
        print(f"After filter: {len(raw_blocks)} blocks.")

    # --------------------------------
    # Adapt Facebook blocks
    # --------------------------------
    print("\nApplying Facebook adapter...")
    adapted = adapt_facebook_blocks(raw_blocks, page_url)

    # --------------------------------
    # Create output folder structure
    # reports/<slug_cleaned>/
    # --------------------------------
    os.makedirs("reports", exist_ok=True)

    raw_slug = slugify_url(page_url)

    # remove www_facebook_com_ prefix
    clean_slug = raw_slug.replace("www_facebook_com_", "")

    folder_path = os.path.join("reports", clean_slug)
    os.makedirs(folder_path, exist_ok=True)

    # File name format:
    # month.day.year_hour.minute.second.html
    dt = datetime.now()
    file_name = dt.strftime("%m.%d.%Y_%H.%M.%S.html")

    out_path = os.path.join(folder_path, file_name)

    # Label for inside report (human readable)
    generated_label = dt.strftime("%Y %B, %d - %H:%M:%S")

    print("\nGenerating HTML PRO report...\n")
    print(f"Report will be written to: {out_path}\n")

    generate_html_report(
        adapted,
        page_url=page_url,
        generated_label=generated_label,
        out_path=out_path
    )

    # --------------------------------
    # Cleanup (Fixes "Event loop is closed")
    # --------------------------------
    print("Cleaning up...")
    try:
        await browser.close()
    except:
        pass

    try:
        await playwright.stop()
    except:
        pass

    print("DONE.\n")


if __name__ == "__main__":
    asyncio.run(main())
