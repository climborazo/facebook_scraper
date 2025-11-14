# facebook_adapter.py
#
# Interprets raw DOM blocks from Facebook into structured posts.
# This is the Facebook-specific logic used by facebook_scraper_pro.

import re
from urllib.parse import urljoin


def clean_author(author_list):
    """Choose the most likely real author."""
    if not author_list:
        return "Unknown Author"

    # Remove common FB noise words
    filtered = []
    for a in author_list:
        if not a:
            continue
        a2 = a.strip()
        if len(a2) < 2:
            continue
        # avoid UI labels
        if a2.lower() in ("comment", "reply", "shared", "share"):
            continue
        filtered.append(a2)

    if not filtered:
        return "Unknown Author"

    # Heuristic: first meaningful one is usually the real author
    return filtered[0]


def clean_timestamp(ts_list):
    """Pick the most usable timestamp string."""
    if not ts_list:
        return ""

    # Facebook often uses aria-label="2 h" or "14 November at 10:23"
    # choose the one with most information
    ts_list_sorted = sorted(ts_list, key=len, reverse=True)
    return ts_list_sorted[0]


def extract_permalink(links, page_url):
    """Try to find a real permalink URL from the post's links."""
    if not links:
        return ""

    for lk in links:
        href = lk.get("href") or ""
        abs_href = urljoin(page_url, href)

        # REAL FACEBOOK POST PERMALINKS
        if "/posts/" in abs_href:
            return abs_href

        if "permalink" in abs_href:
            return abs_href

        # __cft__ URLs hold precise post IDs
        if "__cft__" in abs_href:
            return abs_href

        # multi permalinks
        if "multi_permalinks" in abs_href:
            return abs_href

        # ?__tn__ often used for comments/permalinks
        if "__tn__" in abs_href:
            return abs_href

    # fallback: first absolute link
    return urljoin(page_url, links[0].get("href"))


def extract_text(raw_text):
    """Normalize post text."""
    if not raw_text:
        return ""

    txt = raw_text.strip()

    # Remove excessive linebreaks
    txt = re.sub(r"\n{3,}", "\n\n", txt)

    # Remove WhatsApp-smileys or invisible chars
    txt = txt.replace("\u200b", "").replace("\u200e", "")

    return txt.strip()


def adapt_facebook_blocks(blocks, page_url):
    """
    Takes raw blocks (from core_extractor) and converts them into structured
    Facebook posts.
    """

    structured = []

    for b in blocks:
        # Author
        author = clean_author(b.get("authorCandidates") or [])

        # Timestamp
        timestamp = clean_timestamp(b.get("timestampCandidates") or [])

        # Permalink
        permalink = extract_permalink(b.get("links") or [], page_url)

        # Text
        text = extract_text(b.get("text") or "")

        # Normalize images
        images = []
        for im in b.get("images") or []:
            src = im.get("src") or ""
            if src:
                images.append(src)

        # Normalize links (absolute URLs)
        final_links = []
        for lk in b.get("links") or []:
            href = lk.get("href") or ""
            abs_href = urljoin(page_url, href)
            final_links.append({
                "href": abs_href,
                "text": lk.get("text") or abs_href
            })

        structured.append({
            "post_index": b.get("index"),
            "author": author,
            "text": text,
            "timestamp": timestamp,
            "permalink": permalink,
            "images": images,
            "links": final_links,
            "raw_block": b
        })

    # Sort by author
    structured.sort(key=lambda x: x["author"].lower())

    return structured
