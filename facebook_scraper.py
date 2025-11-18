#!/usr/bin/env python3
"""
Facebook Scraper Deep - Enhanced version with:
- Recursive comment expansion
- Date/period filtering
- Deep thread collection
- Visual nesting in reports
"""

import asyncio
import re
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from core_extractor import extract_raw_blocks
from facebook_adapter import adapt_facebook_blocks
from utils import slugify_url
import os


# ============================================================
# DATE FILTERING UTILITIES
# ============================================================

def parse_facebook_date(timestamp_str: str) -> datetime | None:
    """
    Parse Facebook timestamp formats:
    - "2 h" -> 2 hours ago
    - "3 d" -> 3 days ago
    - "1 w" -> 1 week ago
    - "14 November at 10:23"
    - "Yesterday at 15:30"
    """
    if not timestamp_str:
        return None
    
    ts = timestamp_str.lower().strip()
    now = datetime.now()
    
    # Relative times
    patterns = [
        (r'(\d+)\s*(?:minute|min|m)\s*(?:ago)?', 'minutes'),
        (r'(\d+)\s*(?:hour|h)\s*(?:ago)?', 'hours'),
        (r'(\d+)\s*(?:day|d)\s*(?:ago)?', 'days'),
        (r'(\d+)\s*(?:week|w)\s*(?:ago)?', 'weeks'),
    ]
    
    for pattern, unit in patterns:
        match = re.search(pattern, ts)
        if match:
            value = int(match.group(1))
            if unit == 'minutes':
                return now - timedelta(minutes=value)
            elif unit == 'hours':
                return now - timedelta(hours=value)
            elif unit == 'days':
                return now - timedelta(days=value)
            elif unit == 'weeks':
                return now - timedelta(weeks=value)
    
    # Yesterday
    if 'yesterday' in ts or 'ieri' in ts:
        return now - timedelta(days=1)
    
    # Try parsing full dates (examples: "14 November at 10:23", "Nov 14 at 10:23")
    # This is approximate - Facebook's date format varies by locale
    try:
        # Remove "at HH:MM" part for basic parsing
        date_part = re.sub(r'\s+at\s+\d+:\d+', '', ts)
        for fmt in ['%d %B', '%B %d', '%d %b', '%b %d']:
            try:
                parsed = datetime.strptime(date_part, fmt)
                # Assume current year
                return parsed.replace(year=now.year)
            except ValueError:
                continue
    except:
        pass
    
    return None


def is_within_period(timestamp_str: str, days: int) -> bool:
    """Check if timestamp is within the last N days."""
    if days == 0:  # 0 means no filter
        return True
    
    parsed_date = parse_facebook_date(timestamp_str)
    if not parsed_date:
        # If we can't parse, include it (safer)
        return True
    
    cutoff = datetime.now() - timedelta(days=days)
    return parsed_date >= cutoff


# ============================================================
# DEEP COMMENT EXPANSION
# ============================================================

async def expand_all_comments(page, max_clicks=100, timeout_per_click=3000):
    """
    Recursively expand all comment threads by clicking:
    - "View more replies"
    - "View X more comments"
    - "Show previous comments"
    - etc.
    """
    
    print("\n🔍 Expanding comment threads...")
    
    selectors = [
        # English
        'div[role="button"]:has-text("View more replies")',
        'div[role="button"]:has-text("View more comments")',
        'div[role="button"]:has-text("View previous comments")',
        'span:has-text("more replies")',
        'span:has-text("more comments")',
        
        # Italian
        'div[role="button"]:has-text("Visualizza altre risposte")',
        'div[role="button"]:has-text("Visualizza altri commenti")',
        'div[role="button"]:has-text("Mostra commenti precedenti")',
        
        # Generic patterns
        'div[role="button"][aria-label*="repl"]',
        'div[role="button"][aria-label*="comment"]',
    ]
    
    clicks_made = 0
    iteration = 0
    
    while clicks_made < max_clicks and iteration < 50:
        iteration += 1
        found_any = False
        
        for selector in selectors:
            try:
                # Find all matching buttons
                buttons = await page.query_selector_all(selector)
                
                for button in buttons[:5]:  # Click max 5 per selector per iteration
                    try:
                        # Check if visible
                        is_visible = await button.is_visible()
                        if not is_visible:
                            continue
                        
                        # Click it
                        await button.click(timeout=timeout_per_click)
                        clicks_made += 1
                        found_any = True
                        
                        print(f"   ✓ Clicked expansion button #{clicks_made}")
                        
                        # Wait for content to load
                        await page.wait_for_timeout(1500)
                        
                    except (PlaywrightTimeout, Exception) as e:
                        # Button might have disappeared or become unclickable
                        continue
                        
            except Exception:
                continue
        
        if not found_any:
            print(f"   ℹ️  No more expansion buttons found after {iteration} iterations")
            break
        
        # Scroll a bit to trigger lazy loading
        await page.evaluate("window.scrollBy(0, 500);")
        await page.wait_for_timeout(1000)
    
    print(f"✅ Expansion complete: {clicks_made} buttons clicked\n")


# ============================================================
# ENHANCED HTML REPORT WITH NESTING
# ============================================================

def generate_deep_html_report(posts, page_url, generated_label, out_path, period_filter):
    """Generate HTML report with visual nesting indicators."""
    
    from html import escape as esc
    
    # Group by author
    groups = {}
    for p in posts:
        a = p.get("author") or "Unknown Author"
        groups.setdefault(a, []).append(p)
    
    sorted_authors = sorted(groups.keys(), key=lambda x: x.lower())
    
    h = []
    h.append("<!DOCTYPE html>")
    h.append("<html><head><meta charset='utf-8'><title>Facebook Deep Scraper</title>")
    
    # CSS with nesting indicators
    h.append("""
<style>
body {
    background:#0d1117;
    color:#e6edf3;
    font-family:Segoe UI,Roboto,Arial,sans-serif;
    padding:25px;
}
h1 {
    color:#58a6ff;
    margin-bottom:8px;
}
.subtitle {
    font-size:14px;
    opacity:0.85;
    margin-bottom:20px;
}
.period-badge {
    display:inline-block;
    background:#1f6feb;
    color:#fff;
    padding:4px 10px;
    border-radius:6px;
    font-size:13px;
    margin-left:10px;
}
a { color:#58a6ff; }
.controls {
    display:flex;
    gap:15px;
    flex-wrap:wrap;
    margin:20px 0 25px 0;
}
input[type="text"], select {
    padding:6px 10px;
    background:#161b22;
    border:1px solid #30363d;
    color:#e6edf3;
    border-radius:6px;
}
.author-group {
    margin-top:25px;
    border:1px solid #30363d;
    border-radius:8px;
    background:#161b22;
}
.author-header {
    padding:12px;
    font-size:18px;
    cursor:pointer;
    background:#1d242d;
}
.author-header:hover {
    background:#212c36;
}
.author-body {
    display:none;
    padding:10px 12px;
}
.post-card {
    margin:12px 0;
    background:#0f141a;
    border-left:3px solid #238636;
    border-radius:8px;
    padding:12px;
}
.post-header {
    display:flex;
    justify-content:space-between;
    font-size:14px;
}
.post-meta {
    font-size:12px;
    color:#8b949e;
    margin-top:4px;
}
.post-text {
    margin-top:10px;
    white-space:pre-wrap;
    line-height:1.5;
}
.thumb-img {
    max-width:180px;
    border-radius:6px;
    border:1px solid #30363d;
    margin:4px;
}
.links, .images {
    margin-top:10px;
    font-size:12px;
}
.depth-indicator {
    display:inline-block;
    background:#1f6feb;
    color:#fff;
    padding:2px 8px;
    border-radius:4px;
    font-size:11px;
    margin-left:8px;
}
.stats-bar {
    background:#161b22;
    padding:12px;
    border-radius:6px;
    margin:15px 0;
    font-size:14px;
}
</style>
""")
    
    # JavaScript
    h.append("""
<script>
function toggleGroup(id){
    const el = document.getElementById(id);
    el.style.display = (el.style.display === "none" || !el.style.display) ? "block" : "none";
}

function applyFilters(){
    const textQ = document.getElementById("flt_text").value.toLowerCase();
    const authorQ = document.getElementById("flt_author").value;

    let visibleCount = 0;

    document.querySelectorAll(".author-group").forEach(group=>{
        const author = group.getAttribute("data-author");
        let groupVisible = true;

        if(authorQ !== "ALL" && author !== authorQ){
            groupVisible = false;
        }

        let anyVisible = false;

        group.querySelectorAll(".post-card").forEach(card=>{
            const blob = card.getAttribute("data-search");
            let visible = true;

            if(textQ && !blob.includes(textQ)) visible = false;

            card.style.display = visible ? "" : "none";
            if(visible) {
                anyVisible = true;
                visibleCount++;
            }
        });

        group.style.display = (groupVisible && anyVisible) ? "" : "none";
    });

    document.getElementById("visible_count").textContent = visibleCount;
}

document.addEventListener("DOMContentLoaded", () => {
    let total = document.querySelectorAll(".post-card").length;
    document.getElementById("total_posts").textContent = total;
    document.getElementById("visible_count").textContent = total;
});
</script>
""")
    
    h.append("</head><body>")
    
    # Title
    h.append("<h1>🕵️‍♂️ Facebook Deep Scraper</h1>")
    
    # Period filter badge
    period_text = "All Time" if period_filter == 0 else f"Last {period_filter} days"
    h.append(
        f"<div class='subtitle'>"
        f"<strong>URL:</strong> {esc(page_url)}"
        f"<span class='period-badge'>📅 {period_text}</span>"
        f"</div>"
    )
    
    # Stats bar
    h.append(
        "<div class='stats-bar'>"
        "<strong>Total Posts:</strong> <span id='total_posts'>-</span> | "
        "<strong>Visible:</strong> <span id='visible_count'>-</span> | "
        f"<strong>Generated:</strong> {esc(generated_label)}"
        "</div>"
    )
    
    # Controls
    h.append("<div class='controls'>")
    h.append("<input id='flt_text' type='text' placeholder='Search text...' onkeyup='applyFilters()'>")
    h.append("<select id='flt_author' onchange='applyFilters()'>")
    h.append("<option value='ALL'>All Authors</option>")
    for a in sorted_authors:
        h.append(f"<option value='{esc(a)}'>{esc(a)}</option>")
    h.append("</select>")
    h.append("</div>")
    
    # Author groups
    gid = 0
    for author in sorted_authors:
        posts_list = groups[author]
        gid += 1
        group_id = f"group_{gid}"
        
        h.append(
            f"<div class='author-group' data-author='{esc(author)}'>"
            f"<div class='author-header' onclick=\"toggleGroup('{group_id}')\">"
            f"👤 {esc(author)} <small>({len(posts_list)} posts)</small>"
            f"</div>"
            f"<div class='author-body' id='{group_id}'>"
        )
        
        for p in posts_list:
            idx = p.get("post_index")
            text = p.get("text") or ""
            timestamp = p.get("timestamp") or ""
            permalink = p.get("permalink") or ""
            images = p.get("images") or []
            links = p.get("links") or []
            
            # Estimate nesting depth (heuristic based on text indentation)
            text_lines = text.split('\n')
            leading_spaces = min((len(line) - len(line.lstrip()) for line in text_lines if line.strip()), default=0)
            depth = min(leading_spaces // 4, 5)  # Cap at depth 5
            
            search_blob = f"{text} {author} {timestamp}".lower()
            
            h.append(f"<div class='post-card' data-search='{esc(search_blob)}'>")
            
            h.append(
                f"<div class='post-header'>"
                f"<div><strong>Post {idx}</strong>"
            )
            if depth > 0:
                h.append(f"<span class='depth-indicator'>Depth: {depth}</span>")
            h.append("</div>")
            h.append(f"<div class='post-meta'>🕒 {esc(timestamp)}</div>")
            h.append("</div>")
            
            if permalink:
                h.append(
                    f"<div class='post-meta'>"
                    f"🔗 <a href='{esc(permalink)}' target='_blank'>Permalink</a>"
                    f"</div>"
                )
            
            if text:
                h.append(f"<div class='post-text'>{esc(text)}</div>")
            
            if images:
                h.append("<div class='images'><strong>📷 Images:</strong><br>")
                for src in images[:8]:
                    h.append(
                        f"<a href='{esc(src)}' target='_blank'>"
                        f"<img class='thumb-img' src='{esc(src)}'>"
                        f"</a>"
                    )
                h.append("</div>")
            
            if links:
                h.append("<div class='links'><strong>🔗 Links:</strong>")
                for lk in links[:8]:
                    h.append(
                        f"<div>→ <a href='{esc(lk['href'])}' target='_blank'>{esc(lk['text'])}</a></div>"
                    )
                h.append("</div>")
            
            h.append("</div>")  # post-card
        
        h.append("</div></div>")  # author-body + group
    
    h.append("</body></html>")
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(h))


# ============================================================
# MAIN FUNCTION
# ============================================================

async def main():
    print("\n" + "="*60)
    print("🕵️‍♂️  FACEBOOK DEEP SCRAPER")
    print("="*60 + "\n")
    
    # Period filter
    print("📅 Period Filter:")
    print("   0 = All time")
    print("   1 = Last 24 hours")
    print("   7 = Last week")
    print("   30 = Last month")
    period_input = input("Enter days (0 for all): ").strip()
    period_days = int(period_input) if period_input.isdigit() else 0
    
    # Text filter
    filter_text = input("\n🔍 Filter by text (blank = any): ").strip().lower()
    
    # Auto-scroll
    auto_s = input("\n📜 Auto-scroll? (y/N): ").strip().lower()
    do_scroll = (auto_s == "y")
    
    scroll_steps = 10
    if do_scroll:
        scroll_input = input("   Scroll steps (default 10): ").strip()
        scroll_steps = int(scroll_input) if scroll_input.isdigit() else 10
    
    # Deep expansion
    expand_input = input("\n🔁 Expand all comments recursively? (Y/n): ").strip().lower()
    do_expand = (expand_input != "n")
    
    max_expansion_clicks = 100
    if do_expand:
        clicks_input = input("   Max expansion clicks (default 100): ").strip()
        max_expansion_clicks = int(clicks_input) if clicks_input.isdigit() else 100
    
    print("\n" + "="*60)
    print("🌐 Connecting to Chromium on port 9222...")
    print("   If not running: chromium --remote-debugging-port=9222")
    print("="*60 + "\n")
    
    playwright = await async_playwright().start()
    
    try:
        browser = await playwright.chromium.connect_over_cdp("http://localhost:9222")
    except Exception as e:
        print("❌ Could not connect to Chromium")
        print(f"   Error: {e}\n")
        return
    
    if not browser.contexts:
        print("❌ No active contexts found in Chromium\n")
        return
    
    ctx = browser.contexts[0]
    page = ctx.pages[0]
    page_url = page.url
    
    print(f"✅ Attached to page: {page_url}\n")
    
    # Auto-scroll
    if do_scroll:
        print(f"📜 Scrolling {scroll_steps} steps...")
        for i in range(scroll_steps):
            await page.evaluate("window.scrollBy(0, 1500);")
            await asyncio.sleep(1.5)
            print(f"   Step {i+1}/{scroll_steps}")
        print()
    
    # Deep expansion
    if do_expand:
        await expand_all_comments(page, max_clicks=max_expansion_clicks)
    
    # Extract blocks
    print("🔍 Extracting DOM blocks...")
    raw_blocks = await extract_raw_blocks(page)
    print(f"   Found {len(raw_blocks)} raw blocks\n")
    
    # Text filter
    if filter_text:
        raw_blocks = [
            b for b in raw_blocks
            if filter_text in (b.get("text") or "").lower()
        ]
        print(f"   After text filter: {len(raw_blocks)} blocks\n")
    
    # Adapt to Facebook structure
    print("🔄 Applying Facebook adapter...")
    adapted = adapt_facebook_blocks(raw_blocks, page_url)
    
    # Period filter
    if period_days > 0:
        print(f"📅 Filtering by period (last {period_days} days)...")
        before_count = len(adapted)
        adapted = [
            p for p in adapted
            if is_within_period(p.get("timestamp") or "", period_days)
        ]
        print(f"   Kept {len(adapted)}/{before_count} posts\n")
    
    # Generate output path
    os.makedirs("reports", exist_ok=True)
    raw_slug = slugify_url(page_url)
    clean_slug = raw_slug.replace("www_facebook_com_", "")
    folder_path = os.path.join("reports", clean_slug)
    os.makedirs(folder_path, exist_ok=True)
    
    dt = datetime.now()
    file_name = dt.strftime("%m.%d.%Y_%H.%M.%S.html")
    out_path = os.path.join(folder_path, file_name)
    generated_label = dt.strftime("%Y %B %d - %H:%M:%S")
    
    # Generate report
    print(f"📝 Generating deep HTML report...")
    print(f"   Output: {out_path}\n")
    
    generate_deep_html_report(
        adapted,
        page_url=page_url,
        generated_label=generated_label,
        out_path=out_path,
        period_filter=period_days
    )
    
    print("="*60)
    print("✅ SCRAPING COMPLETE")
    print("="*60)
    print(f"\n📊 Total posts collected: {len(adapted)}")
    print(f"📄 Report saved to: {out_path}\n")
    
    # Cleanup
    try:
        await browser.close()
    except:
        pass
    
    try:
        await playwright.stop()
    except:
        pass


if __name__ == "__main__":
    asyncio.run(main())
