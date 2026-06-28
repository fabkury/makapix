"""Tests for app.utils.bot_detection.is_bot."""

from __future__ import annotations

import pytest

from app.utils.bot_detection import is_bot

# Real-world UA samples lifted from production access logs.
HUMAN_UAS = [
    # Desktop Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # iOS Safari
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    # Firefox
    "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
    # Edge on Android
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36 EdgA/121.0.0.0",
    # MPX physical player firmware
    "Makapix-Player/1.4 (p3a; esp32)",
]

BOT_UAS = [
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",
    "Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)",
    "Twitterbot/1.0",
    "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "WhatsApp/2.23.24.84 A",
    "TelegramBot (like TwitterBot)",
    "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)",
    "Mozilla/5.0 (compatible; SemrushBot/7~bl; +http://www.semrush.com/bot.html)",
    "curl/8.5.0",
    "Wget/1.21.4",
    "python-requests/2.31.0",
    "httpx/0.28.1",
    "Go-http-client/2.0",
]


@pytest.mark.parametrize("ua", HUMAN_UAS)
def test_human_uas_not_bot(ua: str) -> None:
    assert is_bot(ua) is False, f"False positive on {ua!r}"


@pytest.mark.parametrize("ua", BOT_UAS)
def test_bot_uas_detected(ua: str) -> None:
    assert is_bot(ua) is True, f"Missed bot UA {ua!r}"


def test_empty_ua_is_not_bot() -> None:
    assert is_bot("") is False
    assert is_bot(None) is False


def test_partial_match_only_on_word_boundary() -> None:
    # Word-boundary should prevent "robotic" from matching "bot".
    # The regex uses \b so "robot" matches (b at start of word) but a UA that
    # only happens to *contain* the substring without word-boundary should not.
    assert is_bot("Mozilla/5.0 (compatible; SomeRobotic-Browser/1.0)") is False
