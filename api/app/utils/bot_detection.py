"""User-Agent based bot/crawler classification.

Used by the download-stats rollup (and any future consumer that needs to
separate human browser traffic from automated fetches). Deliberately
conservative: matches the well-known crawler families and CLI tools; does
NOT try to fingerprint headless browsers.
"""

from __future__ import annotations

import re

# One regex over the union of patterns is cheaper than N separate searches.
# Word-boundaries keep "discordbot" from matching inside otherwise innocent
# substrings while still tolerating slash/space delimiters that follow.
_BOT_PATTERN = re.compile(
    r"\b(" r"bot|crawler|spider|scraper|"
    # Major search-engine and social embed crawlers
    r"googlebot|bingbot|yandex|baidu|slurp|duckduckbot|"
    r"facebookexternalhit|twitterbot|discordbot|telegrambot|"
    r"whatsapp|linkedinbot|"
    # CLI / library user-agents
    r"curl|wget|python-requests|httpx|go-http-client|"
    # SEO / commercial crawlers
    r"ahrefsbot|semrushbot|mj12bot|dotbot|petalbot|applebot" r")\b",
    re.IGNORECASE,
)


def is_bot(user_agent: str | None) -> bool:
    """Return True iff `user_agent` matches a known bot/crawler pattern.

    Empty / missing User-Agent is treated as human (not bot) to avoid
    over-filtering — many legitimate fetches lack a UA header.
    """
    if not user_agent:
        return False
    return bool(_BOT_PATTERN.search(user_agent))
