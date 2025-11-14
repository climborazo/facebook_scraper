# utils.py
#
# Common helper functions used by the Facebook Scraper PRO project.

import re


def normalize(s: str) -> str:
    """Remove invisible chars, normalize whitespace."""
    if not s:
        return ""
    # Remove zero-width characters
    for ch in ["\u200b", "\u200e", "\u200f", "\u202a", "\u202b", "\u202c"]:
        s = s.replace(ch, "")
    # Collapse whitespace
    s = " ".join(s.split())
    return s.strip()


def normalize_lower(s: str) -> str:
    """Lowercase normalized text."""
    return normalize(s).lower()


def html_escape(text: str) -> str:
    """Minimal HTML escaping."""
    if text is None:
        return ""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


def slugify_url(url: str) -> str:
    """
    Convert a URL into a filesystem-safe slug.
    Example:
        https://www.facebook.com/GroupName/?id=123
        ->
        www_facebook_com_GroupName_id_123
    """
    if not url:
        return "page"
    url = url.strip()
    # Remove scheme
    url = re.sub(r"^https?://", "", url)
    # Replace non-alphanumeric sequences with underscores
    url = re.sub(r"[^A-Za-z0-9]+", "_", url)
    # Collapse multiple underscores
    url = re.sub(r"_+", "_", url)
    return url.strip("_") or "page"


def safe_get(d: dict, key, default=None):
    """Small helper to read dictionary keys safely."""
    try:
        return d.get(key, default)
    except Exception:
        return default
