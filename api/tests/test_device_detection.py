"""Tests for app.utils.view_tracking.detect_device_type (docs/app-device-type/)."""

from __future__ import annotations

import pytest

from app.utils.bot_detection import is_bot
from app.utils.view_tracking import DeviceType, detect_device_type

CASES = [
    # Browsers
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        DeviceType.DESKTOP,
    ),
    (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
        DeviceType.MOBILE,
    ),
    (
        "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
        DeviceType.MOBILE,
    ),
    (
        "Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/604.1",
        DeviceType.TABLET,
    ),
    (
        "Mozilla/5.0 (Linux; Android 13; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        DeviceType.TABLET,
    ),
    # Physical player firmware
    ("Makapix-Player/1.4 (p3a; esp32)", DeviceType.PLAYER),
    # p3a UA contract (docs/p3a/ message 0001): `p3a/<firmware>[ (<free-form>)]`
    ("p3a/1.2.1", DeviceType.PLAYER),
    ("p3a/1.3.0 (esp32-s3; unregistered)", DeviceType.PLAYER),
    # ESP-IDF default UA is NOT a player: any ESP-IDF project sends it
    ("ESP32 HTTP Client/1.0", DeviceType.DESKTOP),
    # Makapix Club app — UA contract (docs/app-device-type/ message 0001)
    ("MakapixClub/1.9.0 (Android 14; Pixel 8)", DeviceType.APP_ANDROID),
    ("MakapixClub/1.9.0 (Android)", DeviceType.APP_ANDROID),
    ("MakapixClub/1.9.0 (iOS 18.5; iPhone)", DeviceType.APP_IOS),
    ("MakapixClub/1.9.0 (iPadOS 18.5; iPad)", DeviceType.APP_IOS),
    ("MakapixClub/1.9.0", DeviceType.APP),
    ("MakapixClub/1.9.0 (Fuchsia)", DeviceType.APP),
    # Exact strings the app ships (message 0002, makapix-app 58e6586c)
    ("MakapixClub/1.9.0+36 (Android 14; Pixel 8)", DeviceType.APP_ANDROID),
    ("MakapixClub/1.9.0+36 (iOS 18.5; iPhone15,3)", DeviceType.APP_IOS),
    ("MakapixClub/1.9.0+36 (iPadOS 18.5; iPad14,3)", DeviceType.APP_IOS),
    ("MakapixClub/unknown (Android)", DeviceType.APP_ANDROID),
    ("MakapixClub/unknown (iOS)", DeviceType.APP_IOS),
    # Developer desktop builds (not in any store) land in the platform-less bucket
    ("MakapixClub/1.9.0+36 (Windows 10.0.26200)", DeviceType.APP),
    # Makapix Club app — every pre-contract build (dart:io default UA)
    ("Dart/3.12 (dart:io)", DeviceType.APP),
    ("Dart/3.9 (dart:io)", DeviceType.APP),
    # Missing UA
    (None, DeviceType.DESKTOP),
    ("", DeviceType.DESKTOP),
]


@pytest.mark.parametrize("user_agent,expected", CASES)
def test_detect_device_type(user_agent, expected):
    assert detect_device_type(user_agent) is expected


def test_app_ua_is_not_a_bot():
    for ua in ("MakapixClub/1.9.0 (Android 14; Pixel 8)", "Dart/3.12 (dart:io)"):
        assert not is_bot(ua)


def test_player_pattern_does_not_capture_app():
    # "Makapix-Player" and "MakapixClub" share a prefix; the app must never be a player.
    assert detect_device_type("MakapixClub/1.9.0 (Android 14)") is not DeviceType.PLAYER


def test_device_type_values_are_stable():
    # Frontend DEVICE_LABELS (web/src/components/metrics/DeviceGrid.tsx) mirrors this set.
    assert {d.value for d in DeviceType} == {
        "desktop",
        "mobile",
        "tablet",
        "player",
        "app",
        "app_android",
        "app_ios",
    }
