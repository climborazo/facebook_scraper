import asyncio
import json
import csv
import os
import re
from collections import Counter
from datetime import datetime
from urllib.parse import urljoin

from playwright.async_api import async_playwright

try:
    import openpyxl
    from openpyxl import Workbook
except ImportError:
    openpyxl = None


# ----------------------------------------------------------
# Utility
# ----------------------------------------------------------

def normalize(s: str) -> str:
    if not s:
        return ""
    for ch in ["\u200b", "\u200e", "\u200f", "\u202a", "\u202b", "\u202c"]:
        s = s.replace(ch, "")
    return " ".join(s.split()).strip()


def normalize_lower(s: str) -> str:
    return normalize(s).lower()


def html_escape(text: str) -> str:
    if text is None:
        return ""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


def slugify_url(url: str) -> str:
    url = url.strip()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"[^A-Za-z0-9]+", "_", url)
    url = re.sub(r"_+", "_", url).strip("_")
    return url or "page"


# ----------------------------------------------------------
# DOM Extraction JS
# ----------------------------------------------------------

JS_EXTRACT_BLOCKS = r"""
(() => {
    function getDataAttrs(el) {
        const res = {};
        if (!el || !el.attributes) return res;
        for (const attr of el.attributes) {
            if (attr.name.startsWith("data-")) {
                if (Object.keys(res).length < 10) {
                    res[attr.name] = attr.value;
                }
            }
        }
        return res;
    }

    let candidates = Array.from(document.querySelectorAll(
        [
            "article",
            "div[role='article']",
            "div[data-pagelet*='FeedUnit']",
            "li[role='listitem']"
        ].join(",")
    ));

    // Fallback repeated-class heuristic
    if (candidates.length < 5) {
        const root = document.querySelector("main") || document.body;
        const divs = Array.from(root.querySelectorAll("div"));
        const classMap = {};
        for (const d of divs) {
            const cls = d.className || "";
            if (!cls) continue;
            classMap[cls] = (classMap[cls] || 0) + 1;
        }
        const frequent = Object.entries(classMap)
            .filter(([c, count]) => count >= 5)
            .map(([c]) => c);

        const extra = [];
        for (const d of divs) {
            if (!d.className) continue;
            if (frequent.includes(d.className)) {
                extra.push(d);
            }
        }
        candidates = candidates.concat(extra.slice(0, 200));
    }

    candidates = Array.from(new Set(candidates));

    const blocks = [];
    let index = 0;

    for (const el of candidates) {
        index += 1;

        let fullText = "";
        try { fullText = (el.innerText || "").trim(); } catch (e) {}

        const authorCandidates = [];
        try {
            const aEls = el.querySelectorAll(
                "h1 a, h2 a, h3 a, h4 a, strong a, " +
                "a[role='link'], span[dir='auto']"
            );
            for (const a of aEls) {
                const t = (a.innerText || "").trim();
                if (t && !authorCandidates.includes(t) && authorCandidates.length < 5) {
                    authorCandidates.push(t);
                }
            }
        } catch (e) {}

        const timestampCandidates = [];
        try {
            const tEls = el.querySelectorAll(
                "time, abbr[title], abbr[aria-label], span[aria-label], a[aria-label]"
            );
            for (const t of tEls) {
                const dt = t.getAttribute("datetime")
                    || t.getAttribute("title")
                    || t.getAttribute("aria-label")
                    || t.innerText
                    || "";
                const val = dt.trim();
                if (val && !timestampCandidates.includes(val) && timestampCandidates.length < 5) {
                    timestampCandidates.push(val);
                }
            }
        } catch (e) {}

        const links = [];
        try {
            const linkEls = el.querySelectorAll("a[href]");
            for (const a of linkEls) {
                const href = (a.getAttribute("href") || "").trim();
                if (!href) continue;
                const text = (a.innerText || "").trim();
                links.push({ href, text });
                if (links.length >= 30) break;
            }
        } catch (e) {}

        const images = [];
        try {
            const imgEls = el.querySelectorAll("img");
            for (const img of imgEls) {
                let src = (img.getAttribute("src") || img.getAttribute("data-src") || "").trim();
                const srcset = (img.getAttribute("srcset") || "").trim();
                const alt = (img.getAttribute("alt") || "").trim();
                if (!src && !srcset) continue;
                images.push({ src, srcset, alt });
                if (images.length >= 30) break;
            }
        } catch (e) {}

        let blockType = "article";
        let snippet = fullText;
        if (snippet.length > 300) snippet = snippet.slice(0, 297) + "...";

        blocks.push({
            index,
            tag: (el.tagName || "").toLowerCase(),
            role: el.getAttribute("role") || "",
            className: el.className || "",
            blockType,
            dataAttrs: getDataAttrs(el),
            text: fullText,
            snippet,
            textLength: fullText.length,
            authorCandidates,
            timestampCandidates,
            links,
            images
        });
    }

    return blocks;
})();
"""


# ----------------------------------------------------------
# Auto-scroll
# ----------------------------------------------------------

async def auto_scroll(page, steps, delay):
    for _ in range(steps):
        await page.mouse.wheel(0, 2500)
        await page.wait_for_timeout(delay * 1000)


# ----------------------------------------------------------
# MAIN
# ----------------------------------------------------------

async def main():
    print("\n=== GENERIC PAGE ANALYZER ===\n")

    text_filter = input("Filter by text (blank = any): ").strip().lower()

    auto_scroll_choice = input("Auto-scroll? (y/N): ").strip().lower()
    do_scroll = auto_scroll_choice == "y"

    steps = 10
    if do_scroll:
        tmp = input("Scroll steps (default 10): ").strip()
        if tmp.isdigit():
            steps = int(tmp)

    print("\nConnecting to Chromium on port 9222 ...\n")
    print("If not running, start it with:")
    print("   chromium --remote-debugging-port=9222\n")

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0]

        page_url = page.url
        now = datetime.now()
        gen_label = now.strftime("%Y %B, %d - %H:%M:%S")

        page_slug = slugify_url(page_url)
        timestamp = now.strftime("%Y_%m_%d-%H_%M_%S")

        if do_scroll:
            await auto_scroll(page, steps, 1.5)

        print("Extracting DOM…")
        raw_blocks = await page.evaluate(JS_EXTRACT_BLOCKS)
        print("Found", len(raw_blocks), "blocks.")

        # Filtering
        filtered = []
        for b in raw_blocks:
            text = b.get("text") or ""
            if text_filter and text_filter not in normalize_lower(text):
                continue
            filtered.append(b)

        print("Keeping", len(filtered), "blocks.")

        normalized = []
        authors_set = set()

        for b in filtered:
            nb = dict(b)

            authors = b.get("authorCandidates") or []
            primary = authors[0] if authors else ""
            primary = normalize(primary)
            nb["primaryAuthor"] = primary

            if primary:
                authors_set.add(primary)

            # Normalize links
            new_links = []
            link_texts = []
            link_hrefs = []

            for lk in b.get("links") or []:
                href = lk.get("href") or ""
                abs_href = urljoin(page_url, href)
                text = lk.get("text") or ""
                link_texts.append(text)
                link_hrefs.append(abs_href)
                new_links.append({"href": abs_href, "text": text})

            nb["links"] = new_links

            # Normalize images
            new_imgs = []
            image_urls = []
            image_alts = []

            for im in b.get("images") or []:
                src = im.get("src") or ""
                srcset = im.get("srcset") or ""
                alt = im.get("alt") or ""

                if not src and srcset:
                    parts = [p.split()[0] for p in srcset.split(",") if p.strip()]
                    if parts:
                        src = parts[-1]

                if not src:
                    continue

                abs_src = urljoin(page_url, src)
                new_imgs.append({"src": abs_src, "alt": alt})
                image_urls.append(abs_src)
                image_alts.append(alt)

            nb["images"] = new_imgs

            # SEARCH BLOB
            parts = [
                b.get("text") or "",
                b.get("snippet") or "",
                primary,
                " ".join(authors),
                b.get("className") or "",
                b.get("role") or "",
                " ".join(b.get("timestampCandidates") or []),
                " ".join(link_texts),
                " ".join(link_hrefs),
                " ".join(image_urls),
                " ".join(image_alts),
            ]
            nb["searchBlob"] = normalize_lower(" ".join(parts))

            normalized.append(nb)

        # ---------- HTML REPORT ----------
        os.makedirs("reports", exist_ok=True)
        html_name = f"{page_slug}-{timestamp}.html"
        html_path = os.path.join("reports", html_name)

        # Group by author
        groups = {}
        for b in normalized:
            a = b.get("primaryAuthor") or "Unknown Author"
            groups.setdefault(a, []).append(b)

        sorted_authors = sorted(groups.keys(), key=lambda x: x.lower())

        html = []
        html.append("<!DOCTYPE html><html><head><meta charset='utf-8'><title>Report</title>")

        html.append("""
<style>
body {
    background:#0d1117;
    color:#e6edf3;
    font-family:Segoe UI,Roboto, sans-serif;
    padding:20px;
}
h1 { color:#58a6ff; margin-bottom:5px; }
a { color:#58a6ff; }
.meta-small { font-size:14px; opacity:0.8; margin-bottom:12px; }
.controls { display:flex; gap:15px; margin-bottom:20px; }
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
.author-header:hover { background:#212c36; }
.author-body { display:none; padding:10px 12px; }
.block-card {
    margin:10px 0;
    background:#0f141a;
    border:1px solid #30363d;
    border-radius:8px;
    padding:10px 12px;
}
.block-header {
    display:flex;
    justify-content:space-between;
    font-size:14px;
}
.block-meta { font-size:12px; color:#8b949e; }
.snippet { margin-top:6px; }
.technical { margin-top:6px; font-size:12px; }
.links, .images { margin-top:6px; font-size:12px; }
.thumb-img {
    max-width:150px;
    border-radius:6px;
    border:1px solid #30363d;
    margin:4px;
}
</style>
""")

        # JS
        html.append("""
<script>
function applyFilters(){
    const textQ = document.getElementById('flt_text').value.toLowerCase();
    const authorQ = document.getElementById('flt_author').value;

    document.querySelectorAll('.author-group').forEach(group=>{
        const author = group.getAttribute('data-author');
        let groupVisible = true;

        if(authorQ !== 'ALL' && author !== authorQ){
            groupVisible = false;
        }

        let anyVisible = false;

        group.querySelectorAll('.block-card').forEach(card=>{
            const blob = card.getAttribute('data-search');
            let visible = true;

            if(textQ && !blob.includes(textQ)) visible=false;

            card.style.display = visible ? '' : 'none';
            if(visible) anyVisible=true;
        });

        group.style.display = (groupVisible && anyVisible)? '' : 'none';
    });
}

function toggleGroup(id){
    const el=document.getElementById(id);
    el.style.display = (el.style.display==='none'||!el.style.display)? 'block':'none';
}
</script>
""")

        html.append("</head><body>")

        # Header
        html.append("<h1>Generic Page Analyzer Report</h1>")
        html.append(f"<div class='meta-small'><strong>Url:</strong> {html_escape(page_url)}</div>")
        html.append(f"<div class='meta-small'><strong>Generated:</strong> {html_escape(gen_label)}</div>")

        # Controls
        html.append("<div class='controls'>")
        html.append("<input id='flt_text' type='text' placeholder='Search text...' onkeyup='applyFilters()'>")
        html.append("<select id='flt_author' onchange='applyFilters()'>")
        html.append("<option value='ALL'>All authors</option>")
        for a in sorted_authors:
            html.append(f"<option value='{html_escape(a)}'>{html_escape(a)}</option>")
        html.append("</select></div>")

        # Groups
        html.append("<h2>Posts by Author</h2>")

        gid = 0
        for author in sorted_authors:
            posts = groups[author]
            gid += 1
            group_id = f"group_{gid}"

            html.append(
                f"<div class='author-group' data-author='{html_escape(author)}'>"
                f"<div class='author-header' onclick=\"toggleGroup('{group_id}')\">"
                f"{html_escape(author)} ({len(posts)} posts)</div>"
                f"<div class='author-body' id='{group_id}'>"
            )

            for b in posts:
                idx = b["index"]
                snippet = b["snippet"]
                cls = b["className"]
                ts = b.get("timestampCandidates") or []
                links = b.get("links") or []
                images = b.get("images") or []

                html.append(
                    f"<div class='block-card' data-search='{html_escape(b['searchBlob'])}'>"
                )
                html.append(f"<div class='block-header'><div><strong>Post {idx}</strong></div><div class='block-meta'>len={b['textLength']}</div></div>")

                if cls:
                    html.append(f"<div class='technical'>class={html_escape(cls[:100])}</div>")

                if ts:
                    html.append("<div class='technical'>Timestamps: " +
                                ", ".join(html_escape(t) for t in ts) + "</div>")

                html.append(f"<div class='snippet'>{html_escape(snippet)}</div>")

                if links:
                    html.append("<div class='links'><strong>Links:</strong>")
                    for lk in links[:8]:
                        html.append(
                            f"<div>- <a href='{html_escape(lk['href'])}' target='_blank'>{html_escape(lk['text'] or lk['href'])}</a></div>"
                        )
                    html.append("</div>")

                if images:
                    html.append("<div class='images'><strong>Images:</strong><br>")
                    for im in images[:6]:
                        html.append(
                            f"<a href='{html_escape(im['src'])}' target='_blank'>"
                            f"<img class='thumb-img' src='{html_escape(im['src'])}'></a>"
                        )
                    html.append("</div>")

                html.append("</div>")  # block-card

            html.append("</div></div>")  # author-body + group

        html.append("</body></html>")

        with open(html_path, "w", encoding="utf-8") as f:
            f.write("\n".join(html))

        print("Saved HTML:", html_path)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
