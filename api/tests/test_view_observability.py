"""View-ingestion observability tests (docs/artwork-views/ D15)."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest


def test_view_route_422_increments_contract_rejected(client):
    from app.services.view_metrics import get_view_counter

    before = get_view_counter("contract_rejected")
    resp = client.post("/post/123/view", json={"intent": "nonsense"})
    assert resp.status_code == 422
    assert get_view_counter("contract_rejected") == before + 1


def test_other_422s_do_not_count(client):
    from app.services.view_metrics import get_view_counter

    before = get_view_counter("contract_rejected")
    # A validation error on a different endpoint.
    resp = client.post("/auth/register", json={"email": 12345})
    assert resp.status_code == 422
    assert get_view_counter("contract_rejected") == before


def test_health_task_ok_when_quiet(db):
    from app.services.view_metrics import set_view_watermark, utc_today
    from app.tasks import check_view_ingestion_health

    set_view_watermark(db, utc_today() - timedelta(days=1))
    db.commit()

    result = check_view_ingestion_health.apply().get()
    assert result["status"] == "success"
    assert result["level"] == "ok"
    assert result["problems"] == []


def test_health_task_flags_contract_rejections(db):
    from app.services.view_metrics import (
        incr_view_counter,
        set_view_watermark,
        utc_today,
    )
    from app.tasks import check_view_ingestion_health

    set_view_watermark(db, utc_today() - timedelta(days=1))
    db.commit()
    incr_view_counter("contract_rejected")

    result = check_view_ingestion_health.apply().get()
    assert result["level"] == "critical"
    assert any("contract-rejected" in p for p in result["problems"])


def test_health_task_flags_stale_or_missing_watermark(db):
    from app.services.view_metrics import set_view_watermark, utc_today
    from app.tasks import check_view_ingestion_health

    # Missing watermark
    result = check_view_ingestion_health.apply().get()
    assert result["level"] == "critical"
    assert any("missing" in p for p in result["problems"])

    # Stale watermark
    set_view_watermark(db, utc_today() - timedelta(days=5))
    db.commit()
    result = check_view_ingestion_health.apply().get()
    assert result["level"] == "critical"
    assert any("stale" in p for p in result["problems"])


def test_health_task_is_heartbeat_monitored():
    from app.observability import BEAT_HEARTBEATS
    from app.tasks import celery_app

    assert "app.tasks.check_view_ingestion_health" in BEAT_HEARTBEATS
    assert "check-view-ingestion-health" in celery_app.conf.beat_schedule
