"""Tests for the opt-in observability wiring (appraisal O8).

The important guarantees: the heartbeat slugs map to REAL celery task names (so
a rename can't silently break a dead-man's-switch), and everything is a no-op
when the env vars are unset (safe to ship before the accounts exist).
"""

import app.observability as obs


def test_beat_heartbeat_slugs_map_to_real_tasks():
    from app.tasks import celery_app

    registered = set(celery_app.tasks.keys())
    missing = [name for name in obs.BEAT_HEARTBEATS if name not in registered]
    assert not missing, f"heartbeat mapping references unknown tasks: {missing}"


def test_init_sentry_noop_without_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    # Must not raise and must not require sentry_sdk to be importable.
    obs.init_sentry("api")
    obs.init_sentry("worker")


def test_hc_ping_noop_without_key(monkeypatch):
    monkeypatch.delenv("HEALTHCHECKS_PING_KEY", raising=False)

    called = {"n": 0}

    def _boom(*a, **k):
        called["n"] += 1
        raise AssertionError("must not ping without a key")

    import requests

    monkeypatch.setattr(requests, "get", _boom)
    obs._hc_ping("rollup-view-events")
    obs._hc_ping("rollup-view-events", "/fail")
    assert called["n"] == 0


def test_hc_ping_hits_expected_url_when_configured(monkeypatch):
    monkeypatch.setenv("HEALTHCHECKS_PING_KEY", "testkey123")
    seen = {}

    def _capture(url, timeout=None):
        seen["url"] = url

        class _R:
            status_code = 200

        return _R()

    import requests

    monkeypatch.setattr(requests, "get", _capture)
    obs._hc_ping("rollup-view-events", "/start")
    assert seen["url"] == "https://hc-ping.com/testkey123/rollup-view-events/start"
