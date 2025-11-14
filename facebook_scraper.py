
import asyncio
from datetime import datetime
import os
from playwright.async_api import async_playwright

from core_extractor import extract_raw_blocks
from facebook_adapter import adapt_facebook_blocks
from html_reporter import generate_html_report
from utils import slugify_url


async def main():
    print("\nFacebook Scraper\n")

    filter_text = input("Filter By Text (Blank = Any): ").strip().lower()

    auto_s = input("Auto Scroll? (Yes / No): ").strip().lower()
    do_scroll = (auto_s == "y")

    scroll_steps_raw = input("Scroll Steps (Default 10): ").strip()
    scroll_steps = int(scroll_steps_raw) if scroll_steps_raw.isdigit() else 10

    print("\nConnecting To Chromium On Port 9222...")
    print("If Chromium Is Not Running, Start It... (chromium --remote-debugging-port=9222)\n")

    playwright = await async_playwright().start()

    try:
        browser = await playwright.chromium.connect_over_cdp("http://localhost:9222")
    except Exception as e:
        print("❌ Could Not Connect To Chromium.")
        print("Start It... (chromium --remote-debugging-port=9222)")
        print("\nDetails:", e)
        return

    if not browser.contexts:
        print("No Active Contexts Found In Chromium.")
        return

    ctx = browser.contexts[0]
    page = ctx.pages[0]
    page_url = page.url

    print(f"Attached To Page: {page_url}\n")

    if do_scroll:
        print(f"Scrolling {scroll_steps} Steps...\n")
        for i in range(scroll_steps):
            await page.evaluate("window.scrollBy(0,1500);")
            await asyncio.sleep(1.5)

    print("Extracting Raw Dom Blocks...")
    raw_blocks = await extract_raw_blocks(page)
    print(f"Found {len(raw_blocks)} Raw Blocks...")

    if filter_text:
        raw_blocks = [
            b for b in raw_blocks
            if filter_text in (b.get("text") or "").lower()
        ]
        print(f"After Filter: {len(raw_blocks)} Blocks...")

    print("\nApplying Facebook Adapter...")
    adapted = adapt_facebook_blocks(raw_blocks, page_url)

    os.makedirs("reports", exist_ok=True)

    raw_slug = slugify_url(page_url)

    clean_slug = raw_slug.replace("www_facebook_com_", "")

    folder_path = os.path.join("reports", clean_slug)
    os.makedirs(folder_path, exist_ok=True)

    dt = datetime.now()
    file_name = dt.strftime("%m.%d.%Y_%H.%M.%S.html")

    out_path = os.path.join(folder_path, file_name)

    generated_label = dt.strftime("%Y %B, %d - %H:%M:%S")

    print("\nGenerating Html Report...\n")
    print(f"Report Will Be Written To: {out_path}\n")

    generate_html_report(
        adapted,
        page_url=page_url,
        generated_label=generated_label,
        out_path=out_path
    )

    print("Cleaning up...")
    try:
        await browser.close()
    except:
        pass

    try:
        await playwright.stop()
    except:
        pass

    print("Done...\n")


if __name__ == "__main__":
    asyncio.run(main())
