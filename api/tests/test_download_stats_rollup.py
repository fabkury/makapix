"""Tests for the download-stats rollup parsing and the resharding
retirement-streak logic (docs/vault-resharding/PLAN.md §7-§8)."""

import json
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from app import models
from app.services.download_stats import (
    _VAULT_URI_RE,
    VaultHit,
    _iter_vault_hits,
    compute_legacy_streak,
)

KEY = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
DAY = date(2026, 6, 9)
TS = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc).timestamp()


def _entry(
    uri,
    *,
    status=200,
    method="GET",
    host="vault.makapix.club",
    ua="Mozilla/5.0",
    ts=TS,
    logger="http.log.access",
):
    return json.dumps(
        {
            "level": "info",
            "ts": ts,
            "logger": logger,
            "msg": "handled request",
            "status": status,
            "request": {
                "method": method,
                "host": host,
                "uri": uri,
                "headers": {"User-Agent": [ua]},
            },
        }
    )


def _write_log(tmp_path, lines, name="vault-access.log"):
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n")
    return p


class TestUriRegex:
    def test_v1_artwork(self):
        m = _VAULT_URI_RE.match(f"/a4/47/ee/{KEY}.png")
        assert m and m.group("s3") == "ee" and m.group("cls") is None

    def test_v2_artwork(self):
        m = _VAULT_URI_RE.match(f"/24/07/{KEY}.png")
        assert m and m.group("s3") is None

    def test_api_vault_prefix_no_longer_matches(self):
        # The /api/vault serving mount was removed 2026-07-22
        # (docs/remove-api-vault/); only bare vault-subdomain paths count.
        assert not _VAULT_URI_RE.match(f"/api/vault/a4/47/ee/{KEY}.gif")
        assert not _VAULT_URI_RE.match(f"/api/vault/24/07/{KEY}.gif")

    def test_avatar_and_blog_classes(self):
        m = _VAULT_URI_RE.match(f"/avatar/a4/47/ee/{KEY}.jpg")
        assert m and m.group("cls") == "avatar"
        m = _VAULT_URI_RE.match(f"/blog_image/24/07/{KEY}.webp")
        assert m and m.group("cls") == "blog_image"

    def test_upscaled(self):
        m = _VAULT_URI_RE.match(f"/a4/47/ee/{KEY}_upscaled.webp")
        assert m and m.group("upscaled")

    def test_rejects_non_vault_paths(self):
        assert not _VAULT_URI_RE.match("/lander/product/index.html")
        assert not _VAULT_URI_RE.match("/")
        assert not _VAULT_URI_RE.match(f"/a4/47/ee/zz/{KEY}.png")


class TestIterVaultHits:
    def test_yields_download_statuses_and_misses(self, tmp_path):
        log = _write_log(
            tmp_path,
            [
                _entry(f"/a4/47/ee/{KEY}.png", status=200),
                _entry(f"/a4/47/ee/{KEY}.png", status=304),
                _entry(f"/a4/47/ee/{KEY}.png", status=206),
                _entry(f"/a4/47/ee/{KEY}.png", status=404),
                _entry(f"/a4/47/ee/{KEY}.png", status=403),  # excluded
            ],
        )
        hits = list(_iter_vault_hits([log], DAY))
        assert len(hits) == 4
        assert [h.status for h in hits] == [200, 304, 206, 404]
        assert all(h.shard_level == 3 for h in hits)

    def test_head_counts_get_only_filter_does_not_apply_here(self, tmp_path):
        log = _write_log(tmp_path, [_entry(f"/24/07/{KEY}.png", method="HEAD")])
        hits = list(_iter_vault_hits([log], DAY))
        assert len(hits) == 1 and hits[0].method == "HEAD"
        assert hits[0].shard_level == 2

    def test_post_excluded(self, tmp_path):
        log = _write_log(tmp_path, [_entry(f"/24/07/{KEY}.png", method="POST")])
        assert list(_iter_vault_hits([log], DAY)) == []

    def test_query_string_stripped(self, tmp_path):
        log = _write_log(tmp_path, [_entry(f"/24/07/{KEY}.png?t=12345")])
        hits = list(_iter_vault_hits([log], DAY))
        assert len(hits) == 1

    def test_day_window(self, tmp_path):
        other_day = TS + 86400 * 2
        log = _write_log(
            tmp_path,
            [
                _entry(f"/24/07/{KEY}.png"),
                _entry(f"/24/07/{KEY}.png", ts=other_day),
            ],
        )
        assert len(list(_iter_vault_hits([log], DAY))) == 1

    def test_non_access_logger_entries_skipped(self, tmp_path):
        log = _write_log(
            tmp_path,
            [_entry(f"/24/07/{KEY}.png", logger="http.handlers.reverse_proxy")],
        )
        assert list(_iter_vault_hits([log], DAY)) == []

    def test_named_access_logger_outputs_counted(self, tmp_path):
        """Sites with their own log directive (the vault subdomains) tag
        entries http.log.access.log0/.log1 — these must count (prod bug
        found at deploy: an exact match dropped every vault entry)."""
        log = _write_log(
            tmp_path,
            [
                _entry(f"/a4/47/ee/{KEY}.png", logger="http.log.access.log0"),
                _entry(f"/24/07/{KEY}.png", logger="http.log.access.log1"),
            ],
        )
        assert len(list(_iter_vault_hits([log], DAY))) == 2

    def test_bot_classification(self, tmp_path):
        log = _write_log(
            tmp_path,
            [
                _entry(f"/24/07/{KEY}.png", ua="Googlebot/2.1"),
                _entry(f"/24/07/{KEY}.png", ua="Mozilla/5.0"),
            ],
        )
        hits = list(_iter_vault_hits([log], DAY))
        assert [h.bot for h in hits] == [True, False]

    def test_class_and_key_extraction(self, tmp_path):
        log = _write_log(tmp_path, [_entry(f"/avatar/a4/47/ee/{KEY}.png")])
        (hit,) = _iter_vault_hits([log], DAY)
        assert hit == VaultHit(
            asset_class="avatar",
            shard_level=3,
            storage_key=UUID(KEY),
            status=200,
            method="GET",
            bot=False,
        )


def _agg_row(day, cls, level, human=0, bot=0):
    return models.VaultShardingStatsDaily(
        date=day,
        asset_class=cls,
        shard_level=level,
        post_id=None,
        downloads_human=human,
        downloads_bot=bot,
        misses=0,
    )


def _full_day(db, day, *, l2_human=5, l3_human=0, l3_bot=0):
    """Insert a complete liveness-valid day of aggregate rows."""
    for cls in ("artwork", "avatar", "blog_image"):
        db.add(_agg_row(day, cls, 2, human=l2_human if cls == "artwork" else 0))
        db.add(
            _agg_row(
                day,
                cls,
                3,
                human=l3_human if cls == "artwork" else 0,
                bot=l3_bot if cls == "artwork" else 0,
            )
        )


class TestComputeLegacyStreak:
    def test_clean_streak_counts(self, db):
        as_of = date(2026, 6, 9)
        for i in range(5):
            _full_day(db, as_of - timedelta(days=i))
        db.commit()
        assert compute_legacy_streak(db, as_of) == 5

    def test_nonbot_legacy_download_breaks_streak(self, db):
        as_of = date(2026, 6, 9)
        _full_day(db, as_of)
        _full_day(db, as_of - timedelta(days=1), l3_human=1)  # legacy hit
        _full_day(db, as_of - timedelta(days=2))
        db.commit()
        assert compute_legacy_streak(db, as_of) == 1

    def test_bot_legacy_download_does_not_break_streak(self, db):
        as_of = date(2026, 6, 9)
        for i in range(3):
            _full_day(db, as_of - timedelta(days=i), l3_bot=7)
        db.commit()
        assert compute_legacy_streak(db, as_of) == 3

    def test_data_gap_blocks_streak(self, db):
        as_of = date(2026, 6, 9)
        _full_day(db, as_of)
        # as_of - 1 missing entirely: rollup never ran
        _full_day(db, as_of - timedelta(days=2))
        db.commit()
        assert compute_legacy_streak(db, as_of) == 1

    def test_dead_pipeline_day_blocks_streak(self, db):
        """An all-zero day means the instrument is broken, not that traffic
        stopped — it must not extend the streak."""
        as_of = date(2026, 6, 9)
        _full_day(db, as_of)
        _full_day(db, as_of - timedelta(days=1), l2_human=0)  # no traffic at all
        _full_day(db, as_of - timedelta(days=2))
        db.commit()
        assert compute_legacy_streak(db, as_of) == 1

    def test_no_data_at_all(self, db):
        assert compute_legacy_streak(db, date(2026, 6, 9)) == 0
