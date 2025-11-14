# core_extractor.py
#
# Extracts raw blocks from the current DOM using Playwright.
# This is the low-level extractor: no Facebook-specific logic.

import asyncio


# ----------------------------------------------------------
# JS snippet used to extract blocks from the DOM
# ----------------------------------------------------------

EXTRACT_JS = r"""
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

    // Candidate selectors (Facebook + generic)
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
            .filter(([cls, count]) => count >= 5)
            .map(([cls]) => cls);

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

        const tag = (el.tagName || "").toLowerCase();
        const role = el.getAttribute("role") || "";
        const className = el.className || "";
        const dataAttrs = getDataAttrs(el);

        let fullText = "";
        try { fullText = (el.innerText || "").trim(); } catch (e) {}

        let snippet = fullText;
        if (snippet.length > 300) snippet = snippet.slice(0, 297) + "...";

        // Authors
        const authors = [];
        try {
            const aEls = el.querySelectorAll(
                "h1 a, h2 a, h3 a, h4 a, strong a, " +
                "a[role='link'], span[dir='auto']"
            );
            for (const a of aEls) {
                const t = (a.innerText || "").trim();
                if (t && !authors.includes(t) && authors.length < 5) {
                    authors.push(t);
                }
            }
        } catch (e) {}

        // Timestamps
        const timestamps = [];
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
                if (val && !timestamps.includes(val) && timestamps.length < 5) {
                    timestamps.push(val);
                }
            }
        } catch (e) {}

        // Links
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

        // Images
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

        blocks.push({
            "index": index,
            "tag": tag,
            "role": role,
            "className": className,
            "dataAttrs": dataAttrs,
            "text": fullText,
            "snippet": snippet,
            "textLength": fullText.length,
            "authorCandidates": authors,
            "timestampCandidates": timestamps,
            "links": links,
            "images": images,
        });
    }

    return blocks;
})();
"""


# ----------------------------------------------------------
# Python function used by the PRO scraper
# ----------------------------------------------------------

async def extract_raw_blocks(page):
    """Executes JS in the browser context to extract raw blocks."""

    blocks = await page.evaluate(EXTRACT_JS)

    # Normalize empty lists
    for b in blocks:
        if b.get("authorCandidates") is None:
            b["authorCandidates"] = []
        if b.get("timestampCandidates") is None:
            b["timestampCandidates"] = []
        if b.get("links") is None:
            b["links"] = []
        if b.get("images") is None:
            b["images"] = []

    return blocks
