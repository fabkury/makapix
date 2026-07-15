"""Error monitoring (Sentry) and scheduled-task dead-man's-switches (healthchecks.io).

Both are fully OPT-IN and no-op unless their env var is set, so this module is
safe to ship before the accounts exist:
  - SENTRY_DSN            -> unhandled exceptions in the API/worker go to Sentry.
  - HEALTHCHECKS_PING_KEY -> each critical beat task pings a healthchecks.io
    check on start/success/failure, so a task that silently STOPS running (which
    no error tracker sees) trips its dead-man's-switch.

Together they close the "fails silently, discovered by accident" gap behind the
July 2026 appraisal's P0 bugs (rollups dropping data, deletion never completing,
etc. — appraisal O8).
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_HC_BASE = "https://hc-ping.com"

# Celery task name -> healthchecks.io check slug. The critical data tasks: a
# silent stop here loses or corrupts data. Slugs auto-create the check on first
# ping when a project Ping Key is used; set each check's period + grace in the
# healthchecks.io UI to match beat_schedule.
BEAT_HEARTBEATS: dict[str, str] = {
    "app.tasks.rollup_view_events": "rollup-view-events",
    "app.tasks.rollup_site_events": "rollup-site-events",
    "app.tasks.rollup_download_stats": "rollup-download-stats",
    "app.tasks.cleanup_deleted_posts": "cleanup-deleted-posts",
    "app.tasks.cleanup_unverified_accounts": "cleanup-unverified-accounts",
    "app.tasks.cleanup_report_ips": "cleanup-report-ips",
    "app.tasks.cleanup_retired_artwork": "cleanup-retired-artwork",
    "app.tasks.renew_crl_if_needed": "renew-crl",
}


def init_sentry(component: str) -> None:
    """Initialise Sentry for ``component`` ("api" or "worker") if SENTRY_DSN is set.

    Never raises: monitoring must not be able to take the app down.
    """
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return
    try:
        import sentry_sdk

        integrations = []
        if component == "worker":
            from sentry_sdk.integrations.celery import CeleryIntegration

            # monitor_beat_tasks stays off — Sentry Crons free tier caps at 1
            # monitor; healthchecks.io covers the beat schedule instead.
            integrations.append(CeleryIntegration(monitor_beat_tasks=False))

        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("SENTRY_ENVIRONMENT", "unknown"),
            release=(os.getenv("SENTRY_RELEASE") or None),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0") or 0),
            integrations=integrations,
            # This app deliberately minimises PII; don't ship request bodies,
            # headers, cookies, or client IPs to Sentry.
            send_default_pii=False,
        )
        logger.info(
            "Sentry initialised for %s (environment=%s)",
            component,
            os.getenv("SENTRY_ENVIRONMENT", "unknown"),
        )
    except Exception:
        logger.warning(
            "Sentry initialisation failed; continuing without it", exc_info=True
        )


def _hc_ping(slug: str, suffix: str = "") -> None:
    """Best-effort healthchecks.io ping. suffix is "", "/start", or "/fail"."""
    key = os.getenv("HEALTHCHECKS_PING_KEY", "").strip()
    if not key:
        return
    url = f"{_HC_BASE}/{key}/{slug}{suffix}"
    try:
        import requests

        requests.get(url, timeout=5)
    except Exception:
        # A missed ping is itself the signal healthchecks watches for; never let
        # a monitoring hiccup affect the task.
        logger.debug("healthchecks ping failed for %s%s", slug, suffix, exc_info=True)


def register_beat_heartbeats() -> None:
    """Wire Celery signals so mapped beat tasks ping healthchecks.io.

    Called once from the worker at startup. No-op without HEALTHCHECKS_PING_KEY.
    Uses signals (not a decorator) so task bodies stay untouched and the mapping
    is the single source of truth.
    """
    if not os.getenv("HEALTHCHECKS_PING_KEY", "").strip():
        return

    from celery.signals import task_failure, task_prerun, task_success

    @task_prerun.connect(weak=False)
    def _hb_prerun(sender=None, **_kw):
        slug = BEAT_HEARTBEATS.get(getattr(sender, "name", ""))
        if slug:
            _hc_ping(slug, "/start")

    @task_success.connect(weak=False)
    def _hb_success(sender=None, **_kw):
        slug = BEAT_HEARTBEATS.get(getattr(sender, "name", ""))
        if slug:
            _hc_ping(slug)

    @task_failure.connect(weak=False)
    def _hb_failure(sender=None, **_kw):
        slug = BEAT_HEARTBEATS.get(getattr(sender, "name", ""))
        if slug:
            _hc_ping(slug, "/fail")

    logger.info(
        "Beat-task dead-man's-switches registered (%d tasks)", len(BEAT_HEARTBEATS)
    )
