from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
import zipfile
from pathlib import Path
from typing import Any

from celery import Celery
from celery.schedules import crontab
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


DEFAULT_REDIS = "redis://cache:6379/0"

celery_app = Celery(
    "makapix",
    broker=os.getenv("CELERY_BROKER_URL", DEFAULT_REDIS),
    backend=os.getenv("CELERY_RESULT_BACKEND", DEFAULT_REDIS),
)

celery_app.conf.update(
    task_default_queue="default",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,
    worker_max_tasks_per_child=100,
    beat_schedule={
        # --- High-frequency maintenance ----------------------------------
        # These run often enough that the exact wall-clock instant is
        # irrelevant, so they stay as plain second-intervals (anchored to
        # beat start, timezone-independent).
        "mark-stale-players-offline": {
            "task": "app.tasks.mark_stale_players_offline",
            "schedule": 60.0,  # Every minute
            "options": {"queue": "default"},
        },
        "cleanup-expired-stats-cache": {
            "task": "app.tasks.cleanup_expired_stats_cache",
            "schedule": 3600.0,  # Every hour
            "options": {"queue": "default"},
        },
        "cleanup-expired-player-registrations": {
            "task": "app.tasks.cleanup_expired_player_registrations",
            "schedule": 3600.0,  # Every hour
            "options": {"queue": "default"},
        },
        "check-post-hashes": {
            "task": "app.tasks.periodic_check_post_hashes",
            "schedule": 21600.0,  # Every 6 hours
        },
        "cleanup-unverified-accounts": {
            "task": "app.tasks.cleanup_unverified_accounts",
            "schedule": 43200.0,  # Every 12 hours
            "options": {"queue": "default"},
        },
        "check-vault-free-space": {
            "task": "app.tasks.check_vault_free_space",
            "schedule": 21600.0,  # Every 6 hours
            "options": {"queue": "default"},
        },
        # --- Daily jobs: fixed wall-clock times -------------------------------
        # crontab() schedules fire at a fixed local time in the beat timezone
        # (America/New_York), so these all run at the stated US Eastern time
        # year-round, DST-aware. They are staggered across the 01:00-05:00 ET
        # low-traffic window so they don't pile onto the worker (concurrency=2)
        # at once.
        #
        # Ordering for the view/site-event pipeline: rollup_view_events
        # aggregates raw view events into post_stats_daily and then deletes the
        # non-player ones it rolled up (same cutoff, one transaction), so a
        # failed rollup leaves its events intact for the next run to pick up.
        # rollup_site_events consumes the surviving player view events, so it
        # runs after. There is deliberately NO separate cleanup task: a second
        # task with its own `now - 7d` cutoff deleted the ~90-minute band of
        # events that were not yet 7 days old at rollup time but were by cleanup
        # time — permanent, un-rolled-up loss — and it also deleted everything
        # when the rollup failed. The same race already forced the removal of
        # cleanup-old-site-events (below).
        "rollup-view-events": {
            "task": "app.tasks.rollup_view_events",
            "schedule": crontab(minute=0, hour=1),  # 01:00 ET
            "options": {"queue": "default"},
        },
        "rollup-blog-post-view-events": {
            "task": "app.tasks.rollup_blog_post_view_events",
            "schedule": crontab(minute=30, hour=1),  # 01:30 ET
            "options": {"queue": "default"},
        },
        "rollup-site-events": {
            "task": "app.tasks.rollup_site_events",
            "schedule": crontab(minute=0, hour=2),  # 02:00 ET (after view rollup)
            "options": {"queue": "default"},
        },
        # NOTE: cleanup-old-site-events AND cleanup-old-view-events were both
        # removed — each raced its rollup with an independent cutoff and deleted
        # raw events before (or instead of) aggregating them. The rollups own
        # deletion, after aggregation, in the same transaction.
        "rollup-download-stats": {
            "task": "app.tasks.rollup_download_stats",
            # 03:00 ET. 3 AM ET == 07:00 UTC (EDT) / 08:00 UTC (EST), both safely
            # past the UTC midnight boundary, so the prior UTC day this task rolls
            # up (it processes "yesterday") is always complete when it fires.
            "schedule": crontab(minute=0, hour=3),  # 03:00 ET
            "options": {"queue": "default"},
        },
        "cleanup-deleted-posts": {
            "task": "app.tasks.cleanup_deleted_posts",
            "schedule": crontab(minute=30, hour=3),  # 03:30 ET
            "options": {"queue": "default"},
        },
        # No ordering dependency on cleanup-deleted-posts: it sweeps the
        # keys retired by replace-artwork, which are disjoint from any live
        # post's current storage_key.
        "cleanup-retired-artwork": {
            "task": "app.tasks.cleanup_retired_artwork",
            "schedule": crontab(minute=45, hour=3),  # 03:45 ET
            "options": {"queue": "default"},
        },
        "cleanup-expired-auth-tokens": {
            "task": "app.tasks.cleanup_expired_auth_tokens",
            "schedule": crontab(minute=0, hour=4),  # 04:00 ET
            "options": {"queue": "default"},
        },
        # PII minimization (docs/ugc-safety/ D24): null reporter_ip on
        # anonymous reports older than 30 days. No ordering dependency.
        "cleanup-report-ips": {
            "task": "app.tasks.cleanup_report_ips",
            "schedule": crontab(minute=15, hour=4),  # 04:15 ET
            "options": {"queue": "default"},
        },
        "cleanup-expired-bdrs": {
            "task": "app.tasks.cleanup_expired_bdrs",
            "schedule": crontab(minute=30, hour=4),  # 04:30 ET
            "options": {"queue": "default"},
        },
        "renew-crl-if-needed": {
            "task": "app.tasks.renew_crl_if_needed",
            "schedule": crontab(minute=0, hour=5),  # 05:00 ET
            "options": {"queue": "default"},
        },
    },
    # Beat timezone governs every crontab() schedule above: the daily jobs run at
    # fixed times in US Eastern (DST-aware). The high-frequency entries are plain
    # second-intervals and are unaffected by this setting.
    timezone="America/New_York",
)


@celery_app.task(name="app.tasks.check_post_hash", bind=True)
def check_post_hash(self, post_id: str) -> dict[str, Any]:
    """
    Check if a post's vault file hash matches the expected hash.
    Sets non_conformant=True if mismatch detected.
    """
    from . import models, vault
    from .db import SessionLocal

    db = SessionLocal()
    try:
        post = db.query(models.Post).filter(models.Post.id == post_id).first()
        if not post:
            logger.error("Post %s not found", post_id)
            return {"status": "error", "message": "Post not found"}

        if not post.hash:
            logger.info("Post %s has no hash, skipping", post_id)
            return {"status": "skipped", "message": "No expected hash"}

        native_pf = next((f for f in post.files if f.is_native), None)
        if not post.storage_key or not native_pf:
            logger.error("Post %s has no storage_key or native file", post_id)
            return {"status": "error", "message": "No storage info"}

        native_format = native_pf.format

        # Read file from vault and compute hash
        file_path = vault.get_artwork_file_path(
            post.storage_key,
            vault.FORMAT_TO_EXT.get(native_format, f".{native_format}"),
            storage_shard=post.storage_shard,
        )
        if not file_path.exists():
            logger.error("Vault file not found for post %s: %s", post_id, file_path)
            return {"status": "error", "message": "Vault file not found"}

        logger.info("Checking hash for post %s from vault: %s", post_id, file_path)
        file_content = file_path.read_bytes()
        actual_hash = hashlib.sha256(file_content).hexdigest()

        if actual_hash != post.hash:
            logger.warning(
                "Hash mismatch for post %s: expected %s, got %s",
                post_id,
                post.hash,
                actual_hash,
            )

            # Mark as non-conformant
            post.non_conformant = True
            db.commit()

            # Log to audit log (system action)
            # Note: We need a system user or use a special UUID for automated actions
            # For now, we'll skip audit logging for automated hash checks
            # In production, you might want to create a system user or use a special actor_id

            return {
                "status": "mismatch",
                "expected": post.hash,
                "actual": actual_hash,
                "non_conformant": True,
            }
        else:
            logger.info("Hash matches for post %s", post_id)
            # If it was previously non-conformant and now matches, clear the flag
            if post.non_conformant:
                post.non_conformant = False
                db.commit()

            return {
                "status": "match",
                "hash": actual_hash,
            }

    except Exception as e:
        logger.error("Error checking hash for post %s: %s", post_id, str(e))
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.periodic_check_post_hashes", bind=True)
def periodic_check_post_hashes(self) -> dict[str, Any]:
    """
    Periodic task to check post hashes for mismatches.
    Runs every 6 hours (configurable via beat_schedule).

    Checks batches of posts with hash set, marks non-conformant on mismatch.
    """
    from . import models, vault
    from .db import SessionLocal
    from .utils.audit import log_moderation_action, get_system_user_id

    db = SessionLocal()
    try:
        # Get system user ID for audit logging
        system_user_id = get_system_user_id(db)
        # Query posts with hash set, limit to reasonable batch size
        # Check posts that haven't been checked recently or are already non-conformant
        from sqlalchemy import exists

        posts_to_check = (
            db.query(models.Post)
            .filter(
                models.Post.hash.isnot(None),
                models.Post.storage_key.isnot(None),
                exists().where(
                    models.PostFile.post_id == models.Post.id,
                    models.PostFile.is_native == True,
                ),
            )
            .limit(100)
            .all()
        )  # Process 100 at a time

        if not posts_to_check:
            logger.info("No posts to check for hash mismatches")
            return {"status": "success", "checked": 0, "mismatches": 0}

        checked_count = 0
        mismatch_count = 0

        for post in posts_to_check:
            try:
                # Get native format from post files
                native_pf = next((f for f in post.files if f.is_native), None)
                if not native_pf:
                    continue
                native_format = native_pf.format

                # Read file from vault and compute hash
                file_path = vault.get_artwork_file_path(
                    post.storage_key,
                    vault.FORMAT_TO_EXT.get(native_format, f".{native_format}"),
                    storage_shard=post.storage_shard,
                )
                if not file_path.exists():
                    logger.warning(
                        f"Vault file not found for post {post.id}: {file_path}"
                    )
                    continue

                file_content = file_path.read_bytes()
                actual_hash = hashlib.sha256(file_content).hexdigest()

                if actual_hash != post.hash:
                    logger.warning(
                        "Hash mismatch detected for post %s: expected %s, got %s",
                        post.id,
                        post.hash,
                        actual_hash,
                    )

                    # Mark as non-conformant
                    post.non_conformant = True
                    db.commit()
                    mismatch_count += 1

                    # Log to audit log with system user
                    try:
                        log_moderation_action(
                            db=db,
                            actor_id=system_user_id,
                            action="hash_mismatch_detected",
                            target_type="post",
                            target_id=post.id,
                            reason_code="hash_mismatch",
                            note=f"Automated hash check detected mismatch. Expected: {post.hash[:16]}..., Got: {actual_hash[:16]}...",
                        )
                    except Exception as audit_error:
                        logger.error(
                            "Failed to log hash mismatch to audit log: %s", audit_error
                        )
                        # Continue even if audit logging fails

                else:
                    # Hash matches - if previously non-conformant, clear flag
                    if post.non_conformant:
                        logger.info(
                            "Hash now matches for post %s, clearing non_conformant flag",
                            post.id,
                        )
                        post.non_conformant = False
                        db.commit()

                checked_count += 1

            except Exception as e:
                logger.error("Error checking hash for post %s: %s", post.id, str(e))
                # Continue with next post
                continue

        logger.info(
            "Periodic hash check completed: checked %d posts, found %d mismatches",
            checked_count,
            mismatch_count,
        )

        return {
            "status": "success",
            "checked": checked_count,
            "mismatches": mismatch_count,
        }

    except Exception as e:
        logger.error("Error in periodic hash check: %s", str(e))
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.write_view_event",
    bind=True,
    ignore_result=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def write_view_event(self, event_data: dict) -> None:
    """
    Async Celery task to write a view event to the database.

    This task receives serialized event data and creates a ViewEvent record.
    Called asynchronously from record_view() to avoid blocking request handlers.

    Args:
        event_data: Dictionary containing view event fields:
            - post_id: Integer ID (as string)
            - viewer_user_id: Integer ID (as string) or None
            - viewer_ip_hash: SHA256 hash string
            - country_code: ISO country code or None
            - device_type: device type string
            - view_source: view source string
            - view_type: view type string
            - user_agent_hash: SHA256 hash or None
            - referrer_domain: domain string or None
            - created_at: ISO datetime string
            - player_id: Player UUID (as string) or None (player views only)
            - local_datetime: Player's local datetime ISO string or None
            - local_timezone: Player's IANA timezone or None
            - play_order: Play order mode (0-2) or None
            - channel: Channel name or None
            - channel_context: Channel context (user_sqid or hashtag) or None
    """
    from datetime import datetime
    from uuid import UUID
    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        # Parse post_id as int (no longer UUID)
        post_id = int(event_data["post_id"])
        viewer_user_id = (
            int(event_data["viewer_user_id"])
            if event_data.get("viewer_user_id")
            else None
        )

        # Parse player_id as UUID if present
        player_id = None
        if event_data.get("player_id"):
            try:
                player_id = UUID(event_data["player_id"])
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid player_id in event_data: {event_data.get('player_id')}"
                )

        # Parse datetime
        created_at = datetime.fromisoformat(event_data["created_at"])

        # Create view event
        view_event = models.ViewEvent(
            id=uuid.uuid4(),
            post_id=post_id,
            viewer_user_id=viewer_user_id,
            viewer_ip_hash=event_data["viewer_ip_hash"],
            country_code=event_data.get("country_code"),
            device_type=event_data["device_type"],
            view_source=event_data["view_source"],
            view_type=event_data["view_type"],
            user_agent_hash=event_data.get("user_agent_hash"),
            referrer_domain=event_data.get("referrer_domain"),
            created_at=created_at,
            # Player-specific fields (nullable)
            player_id=player_id,
            local_datetime=event_data.get("local_datetime"),
            local_timezone=event_data.get("local_timezone"),
            play_order=event_data.get("play_order"),
            channel=event_data.get("channel"),
            channel_context=event_data.get("channel_context"),
        )

        db.add(view_event)
        db.commit()

        logger.debug(f"Wrote deferred view event for post {post_id}")

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to write deferred view event: {e}", exc_info=True)
        raise  # Re-raise to trigger Celery retry
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.write_blog_post_view_event",
    bind=True,
    ignore_result=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def write_blog_post_view_event(self, event_data: dict) -> None:
    """
    Async Celery task to write a blog post view event to the database.

    This task receives serialized event data and creates a BlogPostViewEvent record.
    Called asynchronously from record_blog_post_view() to avoid blocking request handlers.

    Args:
        event_data: Dictionary containing blog post view event fields:
            - blog_post_id: Integer ID (as string)
            - viewer_user_id: Integer ID (as string) or None
            - viewer_ip_hash: SHA256 hash string
            - country_code: ISO country code or None
            - device_type: device type string
            - view_source: view source string
            - view_type: view type string
            - user_agent_hash: SHA256 hash or None
            - referrer_domain: domain string or None
            - created_at: ISO datetime string
    """
    from datetime import datetime
    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        # Parse blog_post_id as int
        blog_post_id = int(event_data["blog_post_id"])
        viewer_user_id = (
            int(event_data["viewer_user_id"])
            if event_data.get("viewer_user_id")
            else None
        )

        # Parse datetime
        created_at = datetime.fromisoformat(event_data["created_at"])

        # Create blog post view event
        view_event = models.BlogPostViewEvent(
            id=uuid.uuid4(),
            blog_post_id=blog_post_id,
            viewer_user_id=viewer_user_id,
            viewer_ip_hash=event_data["viewer_ip_hash"],
            country_code=event_data.get("country_code"),
            device_type=event_data["device_type"],
            view_source=event_data["view_source"],
            view_type=event_data["view_type"],
            user_agent_hash=event_data.get("user_agent_hash"),
            referrer_domain=event_data.get("referrer_domain"),
            created_at=created_at,
        )

        db.add(view_event)
        db.commit()

        logger.debug(
            f"Wrote deferred blog post view event for blog post {blog_post_id}"
        )

    except Exception as e:
        db.rollback()
        logger.error(
            f"Failed to write deferred blog post view event: {e}", exc_info=True
        )
        raise  # Re-raise to trigger Celery retry
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.write_site_event",
    bind=True,
    ignore_result=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def write_site_event(self, event_data: dict) -> None:
    """
    Async Celery task to write a site event to the database.

    This task receives serialized event data and creates a SiteEvent record.
    Called asynchronously from record_site_event() to avoid blocking request handlers.

    Args:
        event_data: Dictionary containing site event fields:
            - event_type: event type string (page_view, signup, upload, etc.)
            - page_path: URL path string or None
            - visitor_ip_hash: SHA256 hash string
            - user_id: Integer ID (as string) or None
            - device_type: device type string
            - country_code: ISO country code or None
            - referrer_domain: domain string or None
            - event_data: dict with event-specific data or None
            - created_at: ISO datetime string
    """
    from datetime import datetime
    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        # Parse user_id as int (User.id is Integer, not UUID)
        user_id = int(event_data["user_id"]) if event_data.get("user_id") else None

        # Parse datetime
        created_at = datetime.fromisoformat(event_data["created_at"])

        # Create site event
        site_event = models.SiteEvent(
            id=uuid.uuid4(),
            event_type=event_data["event_type"],
            page_path=event_data.get("page_path"),
            visitor_ip_hash=event_data["visitor_ip_hash"],
            user_id=user_id,
            device_type=event_data["device_type"],
            country_code=event_data.get("country_code"),
            referrer_domain=event_data.get("referrer_domain"),
            event_data=event_data.get("event_data"),
            created_at=created_at,
        )

        db.add(site_event)
        db.commit()

        logger.debug(f"Wrote deferred site event: {event_data['event_type']}")

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to write deferred site event: {e}", exc_info=True)
        raise  # Re-raise to trigger Celery retry
    finally:
        db.close()


# ============================================================================
# VIEW TRACKING & STATISTICS TASKS
# ============================================================================


@celery_app.task(name="app.tasks.rollup_view_events", bind=True)
def rollup_view_events(self) -> dict[str, Any]:
    """
    Daily task: Roll up view events older than 7 days into daily aggregates.

    This task:
    1. Selects view events older than 7 days (in batches to avoid memory issues)
    2. Aggregates them by (post_id, date)
    3. Upserts into post_stats_daily table
    4. Deletes the old raw events

    Uses batched processing to handle large datasets without OOM errors.
    Runs daily at 01:00 US Eastern (configured in beat_schedule).
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func, cast, Date
    from . import models
    from .db import SessionLocal
    from .utils.view_tracking import visitor_key

    BATCH_SIZE = 10000  # Process events in batches of 10,000

    db = SessionLocal()
    try:
        logger.info("Starting view events rollup task")

        # Get events older than 7 days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)

        # Count total events to process
        total_count = (
            db.query(func.count(models.ViewEvent.id))
            .filter(models.ViewEvent.created_at < cutoff_date)
            .scalar()
        )

        if total_count == 0:
            logger.info("No old view events to roll up")
            return {"status": "success", "rolled_up": 0, "deleted": 0}

        logger.info(f"Found {total_count} old view events to roll up")

        # Aggregate events by (post_id, date) - process in batches
        aggregates: dict[tuple, dict] = {}  # (post_id, date) -> aggregate data
        processed_count = 0
        offset = 0

        while offset < total_count:
            # Fetch a batch of events
            batch = (
                db.query(models.ViewEvent)
                .filter(models.ViewEvent.created_at < cutoff_date)
                .order_by(models.ViewEvent.id)
                .offset(offset)
                .limit(BATCH_SIZE)
                .all()
            )

            if not batch:
                break

            for event in batch:
                key = (event.post_id, event.created_at.date())

                if key not in aggregates:
                    aggregates[key] = {
                        "total_views": 0,
                        "unique_viewer_keys": set(),
                        "views_by_country": {},
                        "views_by_device": {},
                        "views_by_type": {},
                        "total_views_authenticated": 0,
                        "authenticated_unique_viewer_keys": set(),
                        "views_by_country_authenticated": {},
                        "views_by_device_authenticated": {},
                        "views_by_type_authenticated": {},
                    }

                agg = aggregates[key]
                agg["total_views"] += 1
                agg["unique_viewer_keys"].add(
                    visitor_key(event.viewer_user_id, event.viewer_ip_hash)
                )

                if event.country_code:
                    agg["views_by_country"][event.country_code] = (
                        agg["views_by_country"].get(event.country_code, 0) + 1
                    )

                agg["views_by_device"][event.device_type] = (
                    agg["views_by_device"].get(event.device_type, 0) + 1
                )

                agg["views_by_type"][event.view_type] = (
                    agg["views_by_type"].get(event.view_type, 0) + 1
                )

                # Track authenticated views separately
                if event.viewer_user_id is not None:
                    agg["total_views_authenticated"] += 1
                    agg["authenticated_unique_viewer_keys"].add(
                        visitor_key(event.viewer_user_id, event.viewer_ip_hash)
                    )

                    if event.country_code:
                        agg["views_by_country_authenticated"][event.country_code] = (
                            agg["views_by_country_authenticated"].get(
                                event.country_code, 0
                            )
                            + 1
                        )

                    agg["views_by_device_authenticated"][event.device_type] = (
                        agg["views_by_device_authenticated"].get(event.device_type, 0)
                        + 1
                    )

                    agg["views_by_type_authenticated"][event.view_type] = (
                        agg["views_by_type_authenticated"].get(event.view_type, 0) + 1
                    )

            processed_count += len(batch)
            offset += BATCH_SIZE

            # Clear SQLAlchemy's identity map to free memory
            db.expire_all()

            if processed_count % 50000 == 0:
                logger.info(f"Processed {processed_count}/{total_count} view events")

        # Upsert aggregates into post_stats_daily
        rolled_up = 0
        for (post_id, date), agg in aggregates.items():
            # Check if record exists
            existing = (
                db.query(models.PostStatsDaily)
                .filter(
                    models.PostStatsDaily.post_id == post_id,
                    models.PostStatsDaily.date == date,
                )
                .first()
            )

            if existing:
                # Merge with existing data
                existing.total_views += agg["total_views"]
                existing.unique_viewers += len(agg["unique_viewer_keys"])

                # Merge country data
                existing_countries = dict(existing.views_by_country or {})
                for country, count in agg["views_by_country"].items():
                    existing_countries[country] = (
                        existing_countries.get(country, 0) + count
                    )
                existing.views_by_country = existing_countries

                # Merge device data
                existing_devices = dict(existing.views_by_device or {})
                for device, count in agg["views_by_device"].items():
                    existing_devices[device] = existing_devices.get(device, 0) + count
                existing.views_by_device = existing_devices

                # Merge type data
                existing_types = dict(existing.views_by_type or {})
                for vtype, count in agg["views_by_type"].items():
                    existing_types[vtype] = existing_types.get(vtype, 0) + count
                existing.views_by_type = existing_types

                # Merge authenticated data
                existing.total_views_authenticated += agg["total_views_authenticated"]
                existing.unique_viewers_authenticated += len(
                    agg["authenticated_unique_viewer_keys"]
                )

                existing_countries_auth = dict(
                    existing.views_by_country_authenticated or {}
                )
                for country, count in agg["views_by_country_authenticated"].items():
                    existing_countries_auth[country] = (
                        existing_countries_auth.get(country, 0) + count
                    )
                existing.views_by_country_authenticated = existing_countries_auth

                existing_devices_auth = dict(
                    existing.views_by_device_authenticated or {}
                )
                for device, count in agg["views_by_device_authenticated"].items():
                    existing_devices_auth[device] = (
                        existing_devices_auth.get(device, 0) + count
                    )
                existing.views_by_device_authenticated = existing_devices_auth

                existing_types_auth = dict(existing.views_by_type_authenticated or {})
                for vtype, count in agg["views_by_type_authenticated"].items():
                    existing_types_auth[vtype] = (
                        existing_types_auth.get(vtype, 0) + count
                    )
                existing.views_by_type_authenticated = existing_types_auth
            else:
                # Create new record
                daily_stat = models.PostStatsDaily(
                    post_id=post_id,
                    date=date,
                    total_views=agg["total_views"],
                    unique_viewers=len(agg["unique_viewer_keys"]),
                    views_by_country=agg["views_by_country"],
                    views_by_device=agg["views_by_device"],
                    views_by_type=agg["views_by_type"],
                    total_views_authenticated=agg["total_views_authenticated"],
                    unique_viewers_authenticated=len(
                        agg["authenticated_unique_viewer_keys"]
                    ),
                    views_by_country_authenticated=agg[
                        "views_by_country_authenticated"
                    ],
                    views_by_device_authenticated=agg["views_by_device_authenticated"],
                    views_by_type_authenticated=agg["views_by_type_authenticated"],
                )
                db.add(daily_stat)

            rolled_up += 1

            # Commit in batches to avoid holding too many objects
            if rolled_up % 1000 == 0:
                db.commit()

        # Delete old events (preserve player events for rollup_site_events)
        deleted_count = (
            db.query(models.ViewEvent)
            .filter(
                models.ViewEvent.created_at < cutoff_date,
                models.ViewEvent.device_type != "player",
            )
            .delete(synchronize_session=False)
        )

        db.commit()

        logger.info(
            f"Rolled up {rolled_up} daily aggregates, deleted {deleted_count} old events"
        )
        return {"status": "success", "rolled_up": rolled_up, "deleted": deleted_count}

    except Exception:
        # Raise (not a success-shaped error dict) so Celery records a real
        # failure and alerting fires. The rolled-up events are only deleted in
        # the same transaction as the aggregation, so a failure here leaves the
        # raw events intact for the next run — no data loss, no double count.
        logger.error("Error in rollup_view_events task", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.rollup_blog_post_view_events", bind=True)
def rollup_blog_post_view_events(self) -> dict[str, Any]:
    """
    Daily task: Roll up blog post view events older than 7 days into daily aggregates.

    This task:
    1. Selects blog post view events older than 7 days
    2. Aggregates them by (blog_post_id, date)
    3. Upserts into blog_post_stats_daily table
    4. Deletes the old raw events

    Runs daily at 01:30 US Eastern (configured in beat_schedule).
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func, cast, Date
    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        logger.info("Starting blog post view events rollup task")

        # Get events older than 7 days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)

        # Query events to aggregate, grouped by blog_post_id and date
        old_events = (
            db.query(models.BlogPostViewEvent)
            .filter(models.BlogPostViewEvent.created_at < cutoff_date)
            .all()
        )

        if not old_events:
            logger.info("No old blog post view events to roll up")
            return {"status": "success", "rolled_up": 0, "deleted": 0}

        logger.info(f"Found {len(old_events)} old blog post view events to roll up")

        # Aggregate events by (blog_post_id, date)
        aggregates: dict[tuple, dict] = {}  # (blog_post_id, date) -> aggregate data

        for event in old_events:
            key = (event.blog_post_id, event.created_at.date())

            if key not in aggregates:
                aggregates[key] = {
                    "total_views": 0,
                    "unique_ip_hashes": set(),
                    "views_by_country": {},
                    "views_by_device": {},
                    "views_by_type": {},
                }

            agg = aggregates[key]
            agg["total_views"] += 1
            agg["unique_ip_hashes"].add(event.viewer_ip_hash)

            if event.country_code:
                agg["views_by_country"][event.country_code] = (
                    agg["views_by_country"].get(event.country_code, 0) + 1
                )

            agg["views_by_device"][event.device_type] = (
                agg["views_by_device"].get(event.device_type, 0) + 1
            )

            agg["views_by_type"][event.view_type] = (
                agg["views_by_type"].get(event.view_type, 0) + 1
            )

        # Upsert aggregates into blog_post_stats_daily
        rolled_up = 0
        for (blog_post_id, date), agg in aggregates.items():
            # Check if record exists
            existing = (
                db.query(models.BlogPostStatsDaily)
                .filter(
                    models.BlogPostStatsDaily.blog_post_id == blog_post_id,
                    models.BlogPostStatsDaily.date == date,
                )
                .first()
            )

            if existing:
                # Merge with existing data
                existing.total_views += agg["total_views"]
                existing.unique_viewers += len(agg["unique_ip_hashes"])

                # Merge country data
                existing_countries = dict(existing.views_by_country or {})
                for country, count in agg["views_by_country"].items():
                    existing_countries[country] = (
                        existing_countries.get(country, 0) + count
                    )
                existing.views_by_country = existing_countries

                # Merge device data
                existing_devices = dict(existing.views_by_device or {})
                for device, count in agg["views_by_device"].items():
                    existing_devices[device] = existing_devices.get(device, 0) + count
                existing.views_by_device = existing_devices

                # Merge type data
                existing_types = dict(existing.views_by_type or {})
                for vtype, count in agg["views_by_type"].items():
                    existing_types[vtype] = existing_types.get(vtype, 0) + count
                existing.views_by_type = existing_types
            else:
                # Create new record
                daily_stat = models.BlogPostStatsDaily(
                    blog_post_id=blog_post_id,
                    date=date,
                    total_views=agg["total_views"],
                    unique_viewers=len(agg["unique_ip_hashes"]),
                    views_by_country=agg["views_by_country"],
                    views_by_device=agg["views_by_device"],
                    views_by_type=agg["views_by_type"],
                )
                db.add(daily_stat)

            rolled_up += 1

        # Delete old events
        deleted_count = (
            db.query(models.BlogPostViewEvent)
            .filter(models.BlogPostViewEvent.created_at < cutoff_date)
            .delete(synchronize_session=False)
        )

        db.commit()

        logger.info(
            f"Rolled up {rolled_up} blog post daily aggregates, deleted {deleted_count} old events"
        )
        return {"status": "success", "rolled_up": rolled_up, "deleted": deleted_count}

    except Exception as e:
        logger.error(f"Error in rollup_blog_post_view_events task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.cleanup_expired_stats_cache", bind=True)
def cleanup_expired_stats_cache(self) -> dict[str, Any]:
    """
    Hourly task: Clean up expired stats cache entries from the database.

    Note: Redis cache expires automatically, but we also store cache in
    the post_stats_cache table for persistence. This task cleans up
    expired entries from that table.

    Should run hourly (configured in beat_schedule).
    """
    from datetime import datetime, timezone
    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        logger.info("Starting stats cache cleanup task")

        now = datetime.now(timezone.utc)

        # Delete expired cache entries
        deleted_count = (
            db.query(models.PostStatsCache)
            .filter(models.PostStatsCache.expires_at < now)
            .delete(synchronize_session=False)
        )

        db.commit()

        logger.info(f"Cleaned up {deleted_count} expired stats cache entries")
        return {"status": "success", "deleted": deleted_count}

    except Exception as e:
        logger.error(f"Error in cleanup_expired_stats_cache task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.rollup_site_events", bind=True)
def rollup_site_events(self) -> dict[str, Any]:
    """
    Daily task: Roll up site events older than 7 days into daily aggregates.

    This task:
    1. Selects site events older than 7 days (in batches to avoid memory issues)
    2. Aggregates them by date
    3. Upserts into site_stats_daily table
    4. Deletes the old raw events

    Uses batched processing to handle large datasets without OOM errors.
    Runs daily at 02:00 US Eastern (configured in beat_schedule).
    """
    from datetime import datetime, timedelta, timezone, date
    from sqlalchemy import func
    from . import models
    from .db import SessionLocal
    from .utils.view_tracking import visitor_key

    BATCH_SIZE = 10000  # Process events in batches of 10,000

    db = SessionLocal()
    try:
        logger.info("Starting site events rollup task")

        # Get events older than 7 days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)

        # Count total events to process
        total_count = (
            db.query(func.count(models.SiteEvent.id))
            .filter(models.SiteEvent.created_at < cutoff_date)
            .scalar()
        )

        if total_count == 0:
            logger.info("No old site events to roll up")
            return {"status": "success", "rolled_up": 0, "deleted": 0}

        logger.info(f"Found {total_count} old site events to roll up")

        # Aggregate events by date - process in batches
        aggregates: dict[date, dict] = {}  # date -> aggregate data
        processed_count = 0
        offset = 0

        while offset < total_count:
            # Fetch a batch of events
            batch = (
                db.query(models.SiteEvent)
                .filter(models.SiteEvent.created_at < cutoff_date)
                .order_by(models.SiteEvent.id)
                .offset(offset)
                .limit(BATCH_SIZE)
                .all()
            )

            if not batch:
                break

            for event in batch:
                event_date = event.created_at.date()

                if event_date not in aggregates:
                    aggregates[event_date] = {
                        "total_page_views": 0,
                        "unique_visitor_keys": set(),
                        "new_signups": 0,
                        "new_posts": 0,
                        "total_api_calls": 0,
                        "total_errors": 0,
                        "views_by_page": {},
                        "views_by_country": {},
                        "views_by_device": {},
                        "errors_by_type": {},
                        "top_referrers": {},
                        # Authenticated breakdown
                        "authenticated_page_views": 0,
                        "authenticated_unique_visitor_keys": set(),
                        "authenticated_views_by_page": {},
                        "authenticated_views_by_country": {},
                        "authenticated_views_by_device": {},
                        "authenticated_top_referrers": {},
                    }

                agg = aggregates[event_date]

                # Count by event type
                if event.event_type == "page_view":
                    agg["total_page_views"] += 1
                    agg["unique_visitor_keys"].add(
                        visitor_key(event.user_id, event.visitor_ip_hash)
                    )

                    # Track page path
                    if event.page_path:
                        agg["views_by_page"][event.page_path] = (
                            agg["views_by_page"].get(event.page_path, 0) + 1
                        )

                    # Track country
                    if event.country_code:
                        agg["views_by_country"][event.country_code] = (
                            agg["views_by_country"].get(event.country_code, 0) + 1
                        )

                    # Track device
                    agg["views_by_device"][event.device_type] = (
                        agg["views_by_device"].get(event.device_type, 0) + 1
                    )

                    # Track referrer
                    if event.referrer_domain:
                        agg["top_referrers"][event.referrer_domain] = (
                            agg["top_referrers"].get(event.referrer_domain, 0) + 1
                        )

                    # Track authenticated page views
                    if event.user_id is not None:
                        agg["authenticated_page_views"] += 1
                        agg["authenticated_unique_visitor_keys"].add(
                            visitor_key(event.user_id, event.visitor_ip_hash)
                        )

                        if event.page_path:
                            agg["authenticated_views_by_page"][event.page_path] = (
                                agg["authenticated_views_by_page"].get(
                                    event.page_path, 0
                                )
                                + 1
                            )

                        if event.country_code:
                            agg["authenticated_views_by_country"][
                                event.country_code
                            ] = (
                                agg["authenticated_views_by_country"].get(
                                    event.country_code, 0
                                )
                                + 1
                            )

                        agg["authenticated_views_by_device"][event.device_type] = (
                            agg["authenticated_views_by_device"].get(
                                event.device_type, 0
                            )
                            + 1
                        )

                        if event.referrer_domain:
                            agg["authenticated_top_referrers"][
                                event.referrer_domain
                            ] = (
                                agg["authenticated_top_referrers"].get(
                                    event.referrer_domain, 0
                                )
                                + 1
                            )

                elif event.event_type == "signup":
                    agg["new_signups"] += 1
                elif event.event_type == "upload":
                    agg["new_posts"] += 1
                elif event.event_type == "api_call":
                    agg["total_api_calls"] += 1
                elif event.event_type == "error":
                    agg["total_errors"] += 1
                    # Track error type from event_data
                    if event.event_data and "error_type" in event.event_data:
                        error_type = str(event.event_data["error_type"])
                        agg["errors_by_type"][error_type] = (
                            agg["errors_by_type"].get(error_type, 0) + 1
                        )

            processed_count += len(batch)
            offset += BATCH_SIZE

            # Clear SQLAlchemy's identity map to free memory
            db.expire_all()

            if processed_count % 50000 == 0:
                logger.info(f"Processed {processed_count}/{total_count} site events")

        # ===== AGGREGATE PLAYER VIEW EVENTS =====
        # Process ViewEvent records to get player view statistics
        player_aggregates: dict[date, dict] = {}

        player_view_events = (
            db.query(models.ViewEvent)
            .filter(
                models.ViewEvent.device_type == "player",
                models.ViewEvent.created_at < cutoff_date,
            )
            .all()
        )

        for view_event in player_view_events:
            event_date = view_event.created_at.date()

            if event_date not in player_aggregates:
                player_aggregates[event_date] = {
                    "total_player_views": 0,
                    "player_ids": set(),
                    "views_by_player_id": {},
                }

            pagg = player_aggregates[event_date]
            pagg["total_player_views"] += 1

            if view_event.player_id:
                player_id_str = str(view_event.player_id)
                pagg["player_ids"].add(player_id_str)
                pagg["views_by_player_id"][player_id_str] = (
                    pagg["views_by_player_id"].get(player_id_str, 0) + 1
                )

        # Fetch player names for display in aggregated stats
        all_player_ids = set()
        for pagg in player_aggregates.values():
            all_player_ids.update(pagg["player_ids"])

        player_names = {}
        if all_player_ids:
            from uuid import UUID

            player_uuids = [UUID(pid) for pid in all_player_ids]
            players = (
                db.query(models.Player).filter(models.Player.id.in_(player_uuids)).all()
            )
            player_names = {str(p.id): p.name or str(p.player_key)[:8] for p in players}

        # Convert player_id-based counts to player_name-based counts
        for event_date, pagg in player_aggregates.items():
            views_by_player = {}
            for player_id_str, count in pagg["views_by_player_id"].items():
                player_name = player_names.get(player_id_str, player_id_str[:8])
                views_by_player[player_name] = (
                    views_by_player.get(player_name, 0) + count
                )
            pagg["views_by_player"] = views_by_player

        logger.info(f"Aggregated player views for {len(player_aggregates)} days")

        # Upsert aggregates into site_stats_daily
        rolled_up = 0
        for event_date, agg in aggregates.items():
            # Check if record exists
            existing = (
                db.query(models.SiteStatsDaily)
                .filter(models.SiteStatsDaily.date == event_date)
                .first()
            )

            if existing:
                # Merge with existing data
                existing.total_page_views += agg["total_page_views"]
                existing.unique_visitors += len(agg["unique_visitor_keys"])
                existing.new_signups += agg["new_signups"]
                existing.new_posts += agg["new_posts"]
                existing.total_api_calls += agg["total_api_calls"]
                existing.total_errors += agg["total_errors"]

                # Merge JSON fields
                existing_views_by_page = dict(existing.views_by_page or {})
                for page, count in agg["views_by_page"].items():
                    existing_views_by_page[page] = (
                        existing_views_by_page.get(page, 0) + count
                    )
                existing.views_by_page = existing_views_by_page

                existing_views_by_country = dict(existing.views_by_country or {})
                for country, count in agg["views_by_country"].items():
                    existing_views_by_country[country] = (
                        existing_views_by_country.get(country, 0) + count
                    )
                existing.views_by_country = existing_views_by_country

                existing_views_by_device = dict(existing.views_by_device or {})
                for device, count in agg["views_by_device"].items():
                    existing_views_by_device[device] = (
                        existing_views_by_device.get(device, 0) + count
                    )
                existing.views_by_device = existing_views_by_device

                existing_errors_by_type = dict(existing.errors_by_type or {})
                for error_type, count in agg["errors_by_type"].items():
                    existing_errors_by_type[error_type] = (
                        existing_errors_by_type.get(error_type, 0) + count
                    )
                existing.errors_by_type = existing_errors_by_type

                existing_top_referrers = dict(existing.top_referrers or {})
                for referrer, count in agg["top_referrers"].items():
                    existing_top_referrers[referrer] = (
                        existing_top_referrers.get(referrer, 0) + count
                    )
                existing.top_referrers = existing_top_referrers

                # Merge authenticated breakdown fields
                existing.authenticated_page_views += agg["authenticated_page_views"]
                existing.authenticated_unique_visitors += len(
                    agg["authenticated_unique_visitor_keys"]
                )

                existing_auth_views_by_page = dict(
                    existing.authenticated_views_by_page or {}
                )
                for page, count in agg["authenticated_views_by_page"].items():
                    existing_auth_views_by_page[page] = (
                        existing_auth_views_by_page.get(page, 0) + count
                    )
                existing.authenticated_views_by_page = existing_auth_views_by_page

                existing_auth_views_by_country = dict(
                    existing.authenticated_views_by_country or {}
                )
                for country, count in agg["authenticated_views_by_country"].items():
                    existing_auth_views_by_country[country] = (
                        existing_auth_views_by_country.get(country, 0) + count
                    )
                existing.authenticated_views_by_country = existing_auth_views_by_country

                existing_auth_views_by_device = dict(
                    existing.authenticated_views_by_device or {}
                )
                for device, count in agg["authenticated_views_by_device"].items():
                    existing_auth_views_by_device[device] = (
                        existing_auth_views_by_device.get(device, 0) + count
                    )
                existing.authenticated_views_by_device = existing_auth_views_by_device

                existing_auth_top_referrers = dict(
                    existing.authenticated_top_referrers or {}
                )
                for referrer, count in agg["authenticated_top_referrers"].items():
                    existing_auth_top_referrers[referrer] = (
                        existing_auth_top_referrers.get(referrer, 0) + count
                    )
                existing.authenticated_top_referrers = existing_auth_top_referrers

                # Merge player view aggregates if available
                if event_date in player_aggregates:
                    pagg = player_aggregates[event_date]
                    existing.total_player_views += pagg["total_player_views"]
                    existing.active_players += len(pagg["player_ids"])

                    existing_views_by_player = dict(existing.views_by_player or {})
                    for player_name, count in pagg["views_by_player"].items():
                        existing_views_by_player[player_name] = (
                            existing_views_by_player.get(player_name, 0) + count
                        )
                    existing.views_by_player = existing_views_by_player
            else:
                # Get player aggregates for this date if available
                pagg = player_aggregates.get(event_date, {})

                # Create new record
                daily_stat = models.SiteStatsDaily(
                    date=event_date,
                    total_page_views=agg["total_page_views"],
                    unique_visitors=len(agg["unique_visitor_keys"]),
                    new_signups=agg["new_signups"],
                    new_posts=agg["new_posts"],
                    total_api_calls=agg["total_api_calls"],
                    total_errors=agg["total_errors"],
                    views_by_page=agg["views_by_page"],
                    views_by_country=agg["views_by_country"],
                    views_by_device=agg["views_by_device"],
                    errors_by_type=agg["errors_by_type"],
                    top_referrers=agg["top_referrers"],
                    # Authenticated breakdown
                    authenticated_page_views=agg["authenticated_page_views"],
                    authenticated_unique_visitors=len(
                        agg["authenticated_unique_visitor_keys"]
                    ),
                    authenticated_views_by_page=agg["authenticated_views_by_page"],
                    authenticated_views_by_country=agg[
                        "authenticated_views_by_country"
                    ],
                    authenticated_views_by_device=agg["authenticated_views_by_device"],
                    authenticated_top_referrers=agg["authenticated_top_referrers"],
                    # Player view aggregates
                    total_player_views=pagg.get("total_player_views", 0),
                    active_players=len(pagg.get("player_ids", set())),
                    views_by_player=pagg.get("views_by_player", {}),
                )
                db.add(daily_stat)

            rolled_up += 1

            # Commit in batches to avoid holding too many objects
            if rolled_up % 100 == 0:
                db.commit()

        # Delete old site events
        deleted_count = (
            db.query(models.SiteEvent)
            .filter(models.SiteEvent.created_at < cutoff_date)
            .delete(synchronize_session=False)
        )

        # Delete old player view events (from ViewEvent table)
        deleted_player_views = (
            db.query(models.ViewEvent)
            .filter(
                models.ViewEvent.device_type == "player",
                models.ViewEvent.created_at < cutoff_date,
            )
            .delete(synchronize_session=False)
        )

        db.commit()

        logger.info(
            f"Rolled up {rolled_up} daily site aggregates, "
            f"deleted {deleted_count} old site events, "
            f"deleted {deleted_player_views} old player view events"
        )
        return {
            "status": "success",
            "rolled_up": rolled_up,
            "deleted": deleted_count,
            "deleted_player_views": deleted_player_views,
        }

    except Exception:
        # Raise so a failed rollup is a visible Celery failure, not a
        # success-shaped error dict; surviving raw events roll up next run.
        logger.error("Error in rollup_site_events task", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.cleanup_old_site_events", bind=True)
def cleanup_old_site_events(self) -> dict[str, Any]:
    """
    Daily task: Clean up site events older than 7 days.

    This is a safety net - rollup_site_events should delete events after rolling them up,
    but this ensures any stragglers are cleaned up.

    NOTE: no longer scheduled — removed from beat_schedule because it raced with
    rollup_site_events (deleting raw events before aggregation). Retained for
    manual invocation only.
    """
    from datetime import datetime, timedelta, timezone
    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        logger.info("Starting old site events cleanup task")

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)

        deleted_count = (
            db.query(models.SiteEvent)
            .filter(models.SiteEvent.created_at < cutoff_date)
            .delete(synchronize_session=False)
        )

        db.commit()

        logger.info(f"Cleaned up {deleted_count} old site events")
        return {"status": "success", "deleted": deleted_count}

    except Exception as e:
        logger.error(f"Error in cleanup_old_site_events task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.cleanup_old_view_events", bind=True)
def cleanup_old_view_events(self) -> dict[str, Any]:
    """
    Manual-only cleanup of non-player view events older than 7 days.

    NOT scheduled: as a nightly beat task with its own `now - 7d` cutoff it
    deleted the band of events not yet 7 days old at rollup time (permanent,
    un-rolled-up loss) and deleted everything when the rollup failed. The
    rollups own deletion, after aggregation, in the same transaction. Kept only
    as an operator tool for clearing confirmed post-rollup stragglers by hand.
    """
    from datetime import datetime, timedelta, timezone
    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        logger.info("Starting old view events cleanup task")

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)

        deleted_count = (
            db.query(models.ViewEvent)
            .filter(
                models.ViewEvent.created_at < cutoff_date,
                models.ViewEvent.device_type != "player",
            )
            .delete(synchronize_session=False)
        )

        db.commit()

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old view events")

        return {"status": "success", "deleted": deleted_count}

    except Exception as e:
        logger.error(f"Error in cleanup_old_view_events task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.cleanup_report_ips", bind=True)
def cleanup_report_ips(self) -> dict[str, Any]:
    """
    Daily task: null reporter_ip on reports older than 30 days.

    PII minimization for anonymous reports (docs/ugc-safety/ D24) — the IP is
    only needed short-term for abuse correlation. Runs at 04:15 US Eastern.
    """
    from datetime import datetime, timedelta, timezone
    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)

        updated_count = (
            db.query(models.Report)
            .filter(
                models.Report.reporter_ip.isnot(None),
                models.Report.created_at < cutoff_date,
            )
            .update({"reporter_ip": None}, synchronize_session=False)
        )

        db.commit()

        if updated_count > 0:
            logger.info(f"Nulled reporter_ip on {updated_count} old reports")

        return {"status": "success", "cleared": updated_count}

    except Exception as e:
        logger.error(f"Error in cleanup_report_ips task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.cleanup_expired_player_registrations", bind=True)
def cleanup_expired_player_registrations(self) -> dict[str, Any]:
    """
    Hourly task: Clean up expired pending player registrations.

    Removes players that:
    - Have registration_status = 'pending'
    - Have expired registration codes (registration_code_expires_at < now)
    - Were never successfully registered

    This prevents stale entries from accumulating when users provision
    devices but never complete registration on the website.
    """
    from datetime import datetime, timezone
    from . import models
    from .db import get_session

    db = next(get_session())
    try:
        logger.info("Starting expired player registration cleanup task")

        now = datetime.now(timezone.utc)

        # Find and delete expired pending registrations
        deleted_count = (
            db.query(models.Player)
            .filter(
                models.Player.registration_status == "pending",
                models.Player.registration_code_expires_at < now,
            )
            .delete(synchronize_session=False)
        )

        db.commit()

        if deleted_count > 0:
            logger.info(
                f"Cleaned up {deleted_count} expired pending player registrations"
            )

        return {"status": "success", "deleted": deleted_count}

    except Exception as e:
        logger.error(
            f"Error in cleanup_expired_player_registrations task: {e}", exc_info=True
        )
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.mark_stale_players_offline", bind=True)
def mark_stale_players_offline(self) -> dict[str, Any]:
    """
    Frequent task: Mark players offline if they have not sent a status heartbeat recently.

    This is a safety net in case the player does not send an explicit "offline" status
    (e.g., crash / power loss / network failure / LWT misconfiguration).

    Policy:
    - If a player is marked online but last_seen_at is NULL or older than 3 minutes,
      mark it offline.
    """
    from datetime import datetime, timedelta, timezone

    from . import models
    from .db import get_session

    db = next(get_session())
    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=3)

        q = (
            db.query(models.Player)
            .filter(models.Player.connection_status == "online")
            .filter(
                (models.Player.last_seen_at.is_(None))
                | (models.Player.last_seen_at < cutoff)
            )
        )

        marked_offline = q.update(
            {models.Player.connection_status: "offline"},
            synchronize_session=False,
        )
        db.commit()

        if marked_offline > 0:
            logger.info(
                "Marked %s stale player(s) offline (cutoff=%s)",
                marked_offline,
                cutoff.isoformat(),
            )

        return {
            "status": "success",
            "marked_offline": marked_offline,
            "cutoff": cutoff.isoformat(),
        }
    except Exception as e:
        logger.error("Error in mark_stale_players_offline task: %s", e, exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.cleanup_expired_auth_tokens", bind=True)
def cleanup_expired_auth_tokens(self) -> dict[str, Any]:
    """
    Daily task: Clean up expired authentication tokens from the database.

    Cleans up:
    - Expired or revoked refresh tokens (older than 24 hours past expiry/revocation)
    - Expired email verification tokens (older than 7 days past expiry)
    - Expired/used password reset tokens (older than 7 days past expiry)

    This prevents the database from accumulating stale authentication data
    which could grow unbounded over time.

    Runs daily at 04:00 US Eastern (configured in beat_schedule).
    """
    from datetime import datetime, timezone, timedelta
    from . import models
    from .db import get_session

    db = next(get_session())
    try:
        logger.info("Starting expired auth tokens cleanup task")

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Clean up refresh tokens that are either:
        # - Expired more than 24 hours ago, OR
        # - Revoked more than 24 hours ago
        # We keep recent expired/revoked tokens briefly in case of debugging needs
        refresh_cutoff = now - timedelta(hours=24)

        deleted_refresh = (
            db.query(models.RefreshToken)
            .filter(
                (models.RefreshToken.expires_at < refresh_cutoff)
                | (
                    (models.RefreshToken.revoked == True)
                    & (models.RefreshToken.created_at < refresh_cutoff)
                )
            )
            .delete(synchronize_session=False)
        )

        # Clean up email verification tokens older than 7 days past expiry or already used
        verification_cutoff = now - timedelta(days=7)

        deleted_verification = (
            db.query(models.EmailVerificationToken)
            .filter(
                (models.EmailVerificationToken.expires_at < verification_cutoff)
                | (models.EmailVerificationToken.used_at.isnot(None))
            )
            .delete(synchronize_session=False)
        )

        # Clean up password reset tokens older than 7 days past expiry or already used
        deleted_reset = (
            db.query(models.PasswordResetToken)
            .filter(
                (models.PasswordResetToken.expires_at < verification_cutoff)
                | (models.PasswordResetToken.used_at.isnot(None))
            )
            .delete(synchronize_session=False)
        )

        db.commit()

        total_deleted = deleted_refresh + deleted_verification + deleted_reset

        if total_deleted > 0:
            logger.info(
                f"Cleaned up auth tokens: {deleted_refresh} refresh, "
                f"{deleted_verification} verification, {deleted_reset} password reset"
            )

        return {
            "status": "success",
            "deleted_refresh_tokens": deleted_refresh,
            "deleted_verification_tokens": deleted_verification,
            "deleted_reset_tokens": deleted_reset,
            "total": total_deleted,
        }

    except Exception as e:
        logger.error(f"Error in cleanup_expired_auth_tokens task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(bind=True, name="app.tasks.cleanup_unverified_accounts")
def cleanup_unverified_accounts(self) -> dict[str, Any]:
    """
    Periodic task: Delete user accounts that have not verified their email within 3 days.

    These accounts are created during registration but the user never completed
    email verification. They cannot log in and have no user-generated content
    since authentication is required for content creation.

    Deletes each stale account through the same _purge_user_account helper the
    self-serve deletion uses, so accounts that turn out to have content (the
    "unverified users have no content" assumption is false in real data — e.g.
    provider-provisioned accounts) are handled correctly instead of tripping a
    FK and rolling back the whole batch. One problematic account is skipped and
    logged; it does not abort the rest.

    Should run every 12 hours (configured in beat_schedule).
    """
    from datetime import datetime, timezone, timedelta
    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        logger.info("Starting unverified accounts cleanup task")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = now - timedelta(days=3)

        # Find unverified accounts older than 3 days
        user_ids = [
            uid
            for (uid,) in db.query(models.User.id).filter(
                models.User.email_verified == False, models.User.created_at < cutoff
            )
        ]

        if not user_ids:
            logger.info("No unverified accounts older than 3 days found")
            return {"status": "success", "deleted_accounts": 0}

        logger.info(f"Found {len(user_ids)} unverified accounts to delete")

        deleted = 0
        failed = 0
        for uid in user_ids:
            try:
                _purge_user_account(db, uid)
                deleted += 1
            except Exception:
                logger.exception(f"Failed to delete unverified account {uid}; skipping")
                db.rollback()
                failed += 1

        logger.info(
            f"Cleaned up {deleted} unverified accounts ({failed} failed/skipped)"
        )

        return {
            "status": "success" if failed == 0 else "partial",
            "deleted_accounts": deleted,
            "failed_accounts": failed,
        }

    except Exception:
        # A failure here is the query/setup itself, not a single account.
        # Raise so Celery records a real failure instead of a success-shaped
        # error dict (which is how this task silently "worked" while doing
        # nothing).
        logger.error("Error in cleanup_unverified_accounts task", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="app.tasks.check_vault_free_space")
def check_vault_free_space(self) -> dict[str, Any]:
    """
    Watchdog for vault disk headroom (docs/mkpx-upload/): logs the free
    space every run, warns below 4x the write floor, errors below the floor
    itself (at which point uploads are already being refused cleanly by
    ensure_vault_headroom). Runs every 6 hours.
    """
    from .settings import MAKAPIX_VAULT_MIN_FREE_BYTES
    from .vault import get_vault_free_bytes

    free = get_vault_free_bytes()
    floor = MAKAPIX_VAULT_MIN_FREE_BYTES
    free_mb = free / 1024 / 1024
    if free < floor:
        logger.error(
            f"Vault BELOW free-space floor: {free_mb:.0f} MB free "
            f"(floor {floor / 1024 / 1024:.0f} MB) — uploads are being refused"
        )
        level = "critical"
    elif free < floor * 4:
        logger.warning(f"Vault free space low: {free_mb:.0f} MB free")
        level = "warning"
    else:
        logger.info(f"Vault free space OK: {free_mb:.0f} MB free")
        level = "ok"
    return {"status": "success", "free_bytes": free, "level": level}


@celery_app.task(bind=True, name="app.tasks.cleanup_deleted_posts")
def cleanup_deleted_posts(self) -> dict[str, Any]:
    """
    Daily task: Permanently delete posts that were soft-deleted by users more than 7 days ago.

    This task finds all posts where:
    - deleted_by_user = True
    - deleted_by_user_date < now - 7 days

    And performs permanent deletion (vault file + database record).
    Cascades delete to: comments, reactions, admin_notes, view_events, stats, notifications.

    Runs daily at 03:30 US Eastern (configured in beat_schedule).
    """
    from datetime import datetime, timezone, timedelta
    from . import models
    from .db import get_session
    from . import vault
    from .cache import cache_invalidate

    db = next(get_session())
    try:
        logger.info("Starting deleted posts cleanup task")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = now - timedelta(days=7)

        # Find posts marked for deletion older than 7 days
        posts_to_delete = (
            db.query(models.Post)
            .filter(
                models.Post.deleted_by_user == True,
                models.Post.deleted_by_user_date < cutoff,
            )
            .all()
        )

        if not posts_to_delete:
            logger.info("No deleted posts older than 7 days found")
            return {"status": "success", "deleted_posts": 0}

        logger.info(f"Found {len(posts_to_delete)} posts to permanently delete")

        deleted_count = 0
        errors = []

        for post in posts_to_delete:
            post_id = post.id
            try:
                # Capture storage info BEFORE deleting the row — we remove files
                # only AFTER the DB delete is committed, so a failed delete can
                # never leave a surviving row whose artwork files are gone.
                storage_key = post.storage_key
                storage_shard = post.storage_shard
                formats_to_delete = [pf.format for pf in post.files] or []
                has_mkpx = post.mkpx_file_bytes is not None

                # players.current_post_id is a NO ACTION FK, so a player still
                # showing this post would raise and (with the old batched commit)
                # roll back the whole uncommitted batch, orphaning files that
                # were already unlinked. Null it first.
                db.query(models.Player).filter(
                    models.Player.current_post_id == post_id
                ).update(
                    {models.Player.current_post_id: None}, synchronize_session=False
                )

                # Delete the row and commit per post (cascades to comments,
                # reactions, admin_notes, ...). Per-post commits keep each
                # deletion atomic with respect to its file removal.
                db.delete(post)
                db.commit()
                deleted_count += 1

                # Now remove vault files (best-effort — an orphan here is
                # harmless and self-heals, unlike a broken row).
                if storage_key:
                    try:
                        vault.delete_all_artwork_formats(
                            storage_key,
                            formats_to_delete,
                            storage_shard=storage_shard,
                        )
                        if has_mkpx:
                            vault.delete_mkpx_from_vault(storage_key, storage_shard)
                    except Exception as e:
                        logger.warning(
                            f"Failed to delete vault files for deleted post {post_id}: {e}"
                        )

                if deleted_count % 100 == 0:
                    logger.info(f"Deleted {deleted_count} posts so far...")

            except Exception as e:
                logger.error(f"Error deleting post {post_id}: {e}")
                errors.append({"post_id": post_id, "error": str(e)})
                db.rollback()
                continue

        # Final commit
        db.commit()

        logger.info(f"Permanently deleted {deleted_count} posts")

        # Invalidate caches
        try:
            cache_invalidate("feed:recent:*")
            cache_invalidate("feed:promoted:*")
            cache_invalidate("hashtags:*")
        except Exception as e:
            logger.warning(f"Failed to invalidate caches: {e}")

        return {
            "status": "success",
            "deleted_posts": deleted_count,
            "errors": errors if errors else None,
        }

    except Exception as e:
        logger.error(f"Error in cleanup_deleted_posts task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(bind=True, name="app.tasks.cleanup_retired_artwork")
def cleanup_retired_artwork(self) -> dict[str, Any]:
    """
    Daily task: delete vault files retired by replace-artwork once their
    7-day grace period (RetiredArtwork.delete_after) has passed.

    replace-artwork rotates the post's storage_key, leaving the old key's
    files on disk so cached URLs and laggard player devices keep working for
    7 days. This sweep removes them: every format variant plus the upscaled
    preview from BOTH the canonical and legacy-twin trees (resharding D10 —
    skipping the twin would keep serving "deleted" bytes), and the old
    .mkpx layers file if one was attached.

    This is a deliberate, documented exception to the resharding rule that
    no automation deletes vault files (docs/vault-resharding/ D4): it only
    ever touches keys recorded in retired_artworks, never a live post's.

    Runs daily at 03:45 US Eastern (configured in beat_schedule).
    """
    from datetime import datetime, timezone
    from . import models, vault
    from .db import get_session

    db = next(get_session())
    try:
        logger.info("Starting retired artwork cleanup task")

        # Tz-aware compare: delete_after is DateTime(timezone=True)
        now = datetime.now(timezone.utc)

        due_rows = (
            db.query(models.RetiredArtwork)
            .filter(models.RetiredArtwork.delete_after < now)
            .all()
        )

        if not due_rows:
            logger.info("No retired artwork past its grace period")
            return {"status": "success", "swept": 0}

        logger.info(f"Found {len(due_rows)} retired artwork entries to sweep")

        swept_count = 0
        errors = []

        for row in due_rows:
            try:
                # Union the snapshot with all currently-supported formats:
                # missing files are harmless no-ops, and this also catches
                # files a stale in-flight SSAFPP wrote at the old key after
                # the snapshot was taken.
                formats_to_delete = sorted(
                    set(row.formats or []) | set(vault.FORMAT_TO_EXT.keys())
                )
                try:
                    vault.delete_all_artwork_formats(
                        row.storage_key,
                        formats_to_delete,
                        storage_shard=row.storage_shard,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to delete retired vault files for "
                        f"storage_key {row.storage_key}: {e}"
                    )

                if row.had_mkpx:
                    vault.delete_mkpx_from_vault(row.storage_key, row.storage_shard)

                db.delete(row)
                swept_count += 1

                # Commit in batches of 100 to avoid large transactions
                if swept_count % 100 == 0:
                    db.commit()
                    logger.info(f"Swept {swept_count} retired artworks so far...")

            except Exception as e:
                logger.error(
                    f"Error sweeping retired artwork {row.id} "
                    f"(storage_key {row.storage_key}): {e}"
                )
                errors.append({"retired_artwork_id": row.id, "error": str(e)})
                db.rollback()
                continue

        # Final commit
        db.commit()

        logger.info(f"Swept {swept_count} retired artwork entries")

        return {
            "status": "success",
            "swept": swept_count,
            "errors": errors if errors else None,
        }

    except Exception as e:
        logger.error(f"Error in cleanup_retired_artwork task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


# ============================================================================
# SERVER-SIDE ARTWORK FILE POST-PROCESSING (SSAFPP) TASKS
# ============================================================================


def _is_lossy_webp(file_bytes: bytes) -> bool:
    """
    Detect if a WEBP file uses lossy compression (VP8 codec).

    WEBP files have RIFF header, then WEBP signature, then chunk type:
    - VP8 (lossy) or VP8L (lossless) for static images
    - VP8X (extended) for animated/alpha/metadata, followed by other chunks

    Returns True if the WEBP is lossy, False if lossless.
    """
    if len(file_bytes) < 20:
        return False

    # Check RIFF header
    if file_bytes[0:4] != b"RIFF" or file_bytes[8:12] != b"WEBP":
        return False

    # Check chunk type at offset 12
    chunk_type = file_bytes[12:16]

    if chunk_type == b"VP8 ":
        return True  # Lossy
    elif chunk_type == b"VP8L":
        return False  # Lossless
    elif chunk_type == b"VP8X":
        # Extended format - need to check for VP8 chunk within
        # For simplicity, check if there's a VP8 chunk anywhere
        # (VP8X can contain either VP8 or VP8L data)
        pos = 20  # Skip RIFF header + VP8X header
        while pos < len(file_bytes) - 8:
            if file_bytes[pos : pos + 4] == b"VP8 ":
                return True
            # Skip to next chunk
            if pos + 8 > len(file_bytes):
                break
            chunk_size = int.from_bytes(file_bytes[pos + 4 : pos + 8], "little")
            pos += 8 + chunk_size + (chunk_size % 2)  # Chunks are 2-byte aligned
        return False  # Assume lossless if no VP8 chunk found

    return False  # Unknown format, assume lossless


def _sweep_vault_files_for_deleted_post(
    storage_key, storage_shard: str, post_id: int
) -> None:
    """Best-effort removal of every vault file at a storage key whose post row
    vanished mid-SSAFPP (post/account deletion race).

    The deletion path removes only the formats recorded in post_files at the
    time it ran; variants SSAFPP wrote concurrently are unreachable orphans no
    retirement sweep ever covers (unlike the replace-artwork rotation case).
    The post row is gone, so every file at the key is dead — sweep all
    supported formats plus the upscaled variant.
    """
    from . import vault

    try:
        results = vault.delete_all_artwork_formats(
            storage_key, list(vault.FORMAT_TO_EXT), storage_shard=storage_shard
        )
        removed = sorted(fmt for fmt, deleted in results.items() if deleted)
        logger.info(
            f"SSAFPP orphan sweep for deleted post {post_id} at {storage_key}: "
            f"removed {removed or 'nothing'}"
        )
    except Exception:
        logger.exception(
            f"SSAFPP orphan sweep failed for post {post_id} at {storage_key}"
        )


@celery_app.task(
    name="app.tasks.process_ssafpp",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def process_ssafpp(self, post_id: int) -> dict[str, Any]:
    """
    Server-Side Artwork File Post-Processing (SSAFPP).

    Performs automatic post-processing for uploaded artworks:
    1. File Format Conversion (FFC): Convert to all supported formats
    2. Artwork Upscaling (AU): Create 768px max preview using nearest-neighbor

    Task flow:
    1. Load post by ID, validate it's an artwork
    2. Get source file from vault
    3. Determine target formats based on frame_count:
       - Static (frame_count=1): ['png', 'gif', 'webp', 'bmp']
       - Animated (frame_count>1): ['gif', 'webp']
    4. Convert to each target format (skip native, skip if exists)
    5. Create upscaled version
    6. Update formats_available in database

    Note: Pillow's animated GIF and WebP encoders merge consecutive duplicate
    frames (durations are summed), so converted variants can contain fewer
    frames than post.frame_count. Playback is visually identical; frame_count
    describes the native file only (docs/player/displaying-artwork.md).
    """
    from io import BytesIO
    from PIL import Image

    from . import models, vault
    from .db import get_session

    db = next(get_session())
    task_storage_key = None
    task_storage_shard = None
    try:
        logger.info(f"Starting SSAFPP for post {post_id}")

        # Load post
        post = db.query(models.Post).filter(models.Post.id == post_id).first()

        if not post:
            logger.error(f"Post {post_id} not found")
            return {"status": "error", "message": "Post not found"}

        if post.kind != "artwork":
            logger.info(f"Post {post_id} is not an artwork (kind={post.kind})")
            return {"status": "skipped", "message": "Not an artwork"}

        native_pf = next((f for f in post.files if f.is_native), None)
        if not post.storage_key or not native_pf:
            logger.error(f"Post {post_id} missing storage_key or native file")
            return {"status": "error", "message": "Missing storage info"}

        # Remembered for the pre-commit rotation guard below (the shard too:
        # the post row may be gone by the time the guard needs it)
        task_storage_key = post.storage_key
        task_storage_shard = post.storage_shard

        # Get source file path
        native_format = native_pf.format.lower()
        source_path = vault.get_artwork_file_path(
            post.storage_key,
            vault.FORMAT_TO_EXT.get(native_format, f".{native_format}"),
            storage_shard=post.storage_shard,
        )

        if not source_path.exists():
            logger.error(f"Source file not found for post {post_id}: {source_path}")
            return {"status": "error", "message": "Source file not found"}

        # Read source file
        source_bytes = source_path.read_bytes()
        is_animated = post.frame_count > 1

        # Determine target formats
        if is_animated:
            target_formats = ["gif", "webp"]
        else:
            target_formats = ["png", "gif", "webp", "bmp"]

        formats_available = [native_format]
        conversion_results = {}

        # Open source image
        source_image = Image.open(BytesIO(source_bytes))

        # For animated images, extract all frames
        frames = []
        durations = []
        if is_animated:
            try:
                frame_idx = 0
                while True:
                    source_image.seek(frame_idx)
                    frames.append(source_image.copy())
                    duration = source_image.info.get("duration", 100)
                    durations.append(duration)
                    frame_idx += 1
            except EOFError:
                pass  # End of frames
            source_image.seek(0)  # Reset to first frame

        # Convert to each target format
        for target_format in target_formats:
            if target_format == native_format:
                continue  # Skip native format

            target_path = vault.get_artwork_file_path(
                post.storage_key,
                vault.FORMAT_TO_EXT[target_format],
                storage_shard=post.storage_shard,
            )

            # Skip if already exists. The file write and the PostFile row
            # commit are not atomic — a run that died in between leaves the
            # file on disk with no row, and this branch is the only chance a
            # retry gets to repair that, so recreate the row from disk here.
            if target_path.exists():
                if target_format not in formats_available:
                    formats_available.append(target_format)
                row_exists = (
                    db.query(models.PostFile)
                    .filter(
                        models.PostFile.post_id == post.id,
                        models.PostFile.format == target_format,
                    )
                    .first()
                )
                if row_exists is None:
                    db.add(
                        models.PostFile(
                            post_id=post.id,
                            format=target_format,
                            file_bytes=target_path.stat().st_size,
                            is_native=False,
                        )
                    )
                    conversion_results[target_format] = "exists (healed row)"
                else:
                    conversion_results[target_format] = "exists"
                continue

            try:
                output = BytesIO()

                if is_animated:
                    # Animated conversion
                    if target_format == "gif":
                        # Convert frames to P mode for GIF
                        gif_frames = []
                        for frame in frames:
                            if frame.mode == "RGBA":
                                # Flatten alpha onto white background for GIF
                                rgb_frame = Image.new(
                                    "RGB", frame.size, (255, 255, 255)
                                )
                                rgb_frame.paste(frame, mask=frame.split()[3])
                                gif_frames.append(
                                    rgb_frame.convert(
                                        "P", palette=Image.Palette.ADAPTIVE
                                    )
                                )
                            elif frame.mode == "P":
                                gif_frames.append(frame.copy())
                            else:
                                gif_frames.append(
                                    frame.convert("P", palette=Image.Palette.ADAPTIVE)
                                )

                        gif_frames[0].save(
                            output,
                            format="GIF",
                            save_all=True,
                            append_images=gif_frames[1:],
                            duration=durations,
                            loop=0,
                        )

                    elif target_format == "webp":
                        # Convert frames for WEBP (supports RGBA)
                        webp_frames = []
                        for frame in frames:
                            if frame.mode not in ("RGB", "RGBA"):
                                webp_frames.append(frame.convert("RGBA"))
                            else:
                                webp_frames.append(frame.copy())

                        webp_frames[0].save(
                            output,
                            format="WEBP",
                            save_all=True,
                            append_images=webp_frames[1:],
                            duration=durations,
                            loop=0,
                            lossless=True,
                        )

                else:
                    # Static image conversion
                    img = source_image.copy()

                    if target_format == "png":
                        if img.mode not in ("RGB", "RGBA", "P", "L", "LA"):
                            img = img.convert("RGBA")
                        img.save(output, format="PNG")

                    elif target_format == "gif":
                        if img.mode == "RGBA":
                            # Flatten alpha onto white background
                            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                            rgb_img.paste(img, mask=img.split()[3])
                            img = rgb_img.convert("P", palette=Image.Palette.ADAPTIVE)
                        elif img.mode != "P":
                            img = img.convert("P", palette=Image.Palette.ADAPTIVE)
                        img.save(output, format="GIF")

                    elif target_format == "webp":
                        if img.mode not in ("RGB", "RGBA"):
                            img = img.convert("RGBA")
                        img.save(output, format="WEBP", lossless=True)

                    elif target_format == "bmp":
                        if img.mode not in ("RGB", "L"):
                            if img.mode == "RGBA":
                                # Flatten alpha onto white background
                                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                                rgb_img.paste(img, mask=img.split()[3])
                                img = rgb_img
                            else:
                                img = img.convert("RGB")
                        img.save(output, format="BMP")

                # Write to file (vault primitive: atomic + twin mirror)
                converted_bytes = len(output.getvalue())
                vault.save_artwork_to_vault(
                    post.storage_key,
                    output.getvalue(),
                    target_format,
                    storage_shard=post.storage_shard,
                )
                formats_available.append(target_format)
                conversion_results[target_format] = "created"

                # Create PostFile row for converted format
                pf = models.PostFile(
                    post_id=post.id,
                    format=target_format,
                    file_bytes=converted_bytes,
                    is_native=False,
                )
                db.merge(pf)

                logger.info(f"Created {target_format} for post {post_id}")

            except Exception as e:
                logger.error(
                    f"Failed to convert to {target_format} for post {post_id}: {e}"
                )
                conversion_results[target_format] = f"error: {e}"

        # Create upscaled version
        upscaled_result = "skipped"
        try:
            upscaled_path = vault.get_upscaled_file_path(
                post.storage_key, storage_shard=post.storage_shard
            )

            # Skip if already exists
            if not upscaled_path.exists():
                # Calculate scale factor (largest integer where max dimension <= 768)
                width = post.width or source_image.width
                height = post.height or source_image.height
                max_dim = max(width, height)

                if max_dim <= 768:
                    scale_factor = 768 // max_dim
                else:
                    scale_factor = 1

                if scale_factor > 1:
                    new_width = width * scale_factor
                    new_height = height * scale_factor

                    output = BytesIO()

                    # Determine if output should be lossy or lossless
                    use_lossy = native_format == "webp" and _is_lossy_webp(source_bytes)

                    if is_animated:
                        # MEMORY SAFEGUARD: Cap frame count at 256 for upscaling only.
                        # Upscaling creates larger in-memory frames (e.g., 64x64 -> 768x768),
                        # and processing hundreds of such frames can cause memory exhaustion
                        # in the worker process. The original format conversions above use
                        # the full frame set since they don't increase frame dimensions.
                        # 256 frames at 768x768 RGBA ≈ 600MB which is a reasonable limit.
                        MAX_UPSCALE_FRAMES = 256
                        upscale_frames = frames[:MAX_UPSCALE_FRAMES]
                        upscale_durations = durations[:MAX_UPSCALE_FRAMES]
                        if len(frames) > MAX_UPSCALE_FRAMES:
                            logger.info(
                                f"Capping upscaled animation from {len(frames)} to {MAX_UPSCALE_FRAMES} frames for post {post_id}"
                            )

                        # Upscale all frames (capped)
                        upscaled_frames = []
                        for frame in upscale_frames:
                            if frame.mode not in ("RGB", "RGBA"):
                                frame = frame.convert("RGBA")
                            upscaled_frame = frame.resize(
                                (new_width, new_height),
                                resample=Image.Resampling.NEAREST,
                            )
                            upscaled_frames.append(upscaled_frame)

                        upscaled_frames[0].save(
                            output,
                            format="WEBP",
                            save_all=True,
                            append_images=upscaled_frames[1:],
                            duration=upscale_durations,
                            loop=0,
                            lossless=not use_lossy,
                            quality=90 if use_lossy else 100,
                        )
                    else:
                        # Upscale static image
                        img = source_image.copy()
                        if img.mode not in ("RGB", "RGBA"):
                            img = img.convert("RGBA")

                        upscaled_img = img.resize(
                            (new_width, new_height),
                            resample=Image.Resampling.NEAREST,
                        )

                        upscaled_img.save(
                            output,
                            format="WEBP",
                            lossless=not use_lossy,
                            quality=90 if use_lossy else 100,
                        )

                    vault.save_upscaled_artwork(
                        post.storage_key,
                        output.getvalue(),
                        storage_shard=post.storage_shard,
                    )
                    upscaled_result = (
                        f"created ({new_width}x{new_height}, scale={scale_factor})"
                    )
                    logger.info(
                        f"Created upscaled version for post {post_id}: {upscaled_result}"
                    )
                else:
                    upscaled_result = "skipped (no scaling possible)"
            else:
                upscaled_result = "exists"

        except Exception as e:
            logger.error(f"Failed to create upscaled version for post {post_id}: {e}")
            upscaled_result = f"error: {e}"

        # Guard against replace-artwork committing mid-task: it rotates the
        # storage_key, so everything above targeted the retired key. The
        # vault files land there harmlessly (the retirement sweep deletes
        # every supported format), but the PostFile rows would describe
        # files that don't exist at the new key — and collide with the rows
        # the replace-enqueued SSAFPP run will create. Abort instead.
        current_key = (
            db.query(models.Post.storage_key).filter(models.Post.id == post_id).scalar()
        )
        if current_key != task_storage_key:
            db.rollback()
            if current_key is None:
                # Post row deleted mid-task (post or account deletion).
                # Unlike the rotation case there is no retirement sweep for
                # this key, so the files written above would be orphaned
                # forever — remove them now.
                logger.info(f"SSAFPP for post {post_id} aborted: post deleted mid-task")
                _sweep_vault_files_for_deleted_post(
                    task_storage_key, task_storage_shard, post_id
                )
                return {"status": "skipped", "message": "post deleted mid-task"}
            logger.info(
                f"SSAFPP for post {post_id} aborted: storage_key rotated "
                f"mid-task ({task_storage_key} -> {current_key})"
            )
            return {"status": "skipped", "message": "storage_key rotated mid-task"}

        # Commit PostFile rows created during conversion
        db.commit()

        final_formats = sorted(set(formats_available))
        logger.info(f"SSAFPP completed for post {post_id}: formats={final_formats}")

        return {
            "status": "success",
            "post_id": post_id,
            "formats_available": final_formats,
            "conversions": conversion_results,
            "upscaled": upscaled_result,
        }

    except Exception as e:
        logger.error(f"SSAFPP failed for post {post_id}: {e}", exc_info=True)
        db.rollback()
        # A mid-task post deletion can also land here (e.g. FK violation when
        # flushing PostFile rows after the post row vanished). A retry would
        # bail on "Post not found" without cleaning up, stranding the files
        # this run already wrote — sweep them and skip instead.
        if task_storage_key is not None:
            try:
                post_gone = (
                    db.query(models.Post.id).filter(models.Post.id == post_id).scalar()
                    is None
                )
            except Exception:
                post_gone = False  # can't tell; leave it to the retry
            if post_gone:
                _sweep_vault_files_for_deleted_post(
                    task_storage_key, task_storage_shard, post_id
                )
                return {"status": "skipped", "message": "post deleted mid-task"}
        raise  # Re-raise for Celery retry

    finally:
        db.close()


# ============================================================================
# POST MANAGEMENT DASHBOARD (PMD) TASKS
# ============================================================================


@celery_app.task(
    name="app.tasks.process_bdr_job",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    retry_backoff_max=600,  # Max 10 minutes between retries
)
def process_bdr_job(self, bdr_id: str) -> dict[str, Any]:
    """
    Process a Batch Download Request: build ZIP file with artworks.

    Steps:
    1. Load BDR record and validate
    2. Update status to 'processing'
    3. Fetch all post data
    4. Download artwork files from vault/URLs
    5. Build ZIP with artworks + metadata JSON files
    6. Save ZIP to vault
    7. Update BDR record with file info
    8. Send email notification (if requested)
    9. Update status to 'ready'

    On failure:
    - Update status to 'failed' with error message
    - Celery will retry up to 3 times with exponential backoff
    """
    import shutil
    import tempfile
    from datetime import datetime, timezone, timedelta
    from uuid import UUID

    from sqlalchemy import func

    from . import models, vault
    from .db import SessionLocal
    from .sqids_config import sqids

    db = SessionLocal()
    try:
        logger.info(f"Processing BDR job: {bdr_id}")

        # Load BDR
        bdr_uuid = UUID(bdr_id)
        bdr = (
            db.query(models.BatchDownloadRequest)
            .filter(models.BatchDownloadRequest.id == bdr_uuid)
            .first()
        )

        if not bdr:
            logger.error(f"BDR {bdr_id} not found")
            return {"status": "error", "message": "BDR not found"}

        if bdr.status not in ("pending", "processing"):
            logger.info(f"BDR {bdr_id} already processed (status: {bdr.status})")
            return {"status": "skipped", "message": f"Already {bdr.status}"}

        # Update status to processing
        bdr.status = "processing"
        bdr.started_at = datetime.now(timezone.utc)
        db.commit()

        # Load user info
        user = db.query(models.User).filter(models.User.id == bdr.user_id).first()
        if not user:
            raise ValueError("User not found")

        user_sqid = user.public_sqid or sqids.encode([user.id])

        # Load posts with their data
        posts = db.query(models.Post).filter(models.Post.id.in_(bdr.post_ids)).all()

        if not posts:
            raise ValueError("No posts found")

        # Build metadata
        metadata = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "user_handle": user.handle,
            "artwork_count": len(posts),
            "artworks": [],
        }

        # Load comments if requested
        comments_data = None
        if bdr.include_comments:
            comments = (
                db.query(models.Comment)
                .filter(
                    models.Comment.post_id.in_(bdr.post_ids),
                    models.Comment.hidden_by_mod == False,
                    models.Comment.deleted_by_owner == False,
                    models.Comment.deleted_by_mod == False,
                )
                .all()
            )

            # Group by post_id, then by post_sqid
            comments_by_post = {}
            post_id_to_sqid = {p.id: p.public_sqid for p in posts}

            for comment in comments:
                sqid = post_id_to_sqid.get(comment.post_id)
                if sqid:
                    if sqid not in comments_by_post:
                        comments_by_post[sqid] = []

                    # Get author handle
                    author_handle = None
                    if comment.author_id:
                        author = (
                            db.query(models.User.handle)
                            .filter(models.User.id == comment.author_id)
                            .first()
                        )
                        author_handle = author[0] if author else "anonymous"
                    else:
                        author_handle = "anonymous"

                    comments_by_post[sqid].append(
                        {
                            "id": str(comment.id),
                            "author_handle": author_handle,
                            "body": comment.body,
                            "created_at": comment.created_at.isoformat(),
                        }
                    )

            comments_data = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "comments_by_artwork": comments_by_post,
            }

        # Load reactions if requested
        reactions_data = None
        if bdr.include_reactions:
            reactions = (
                db.query(
                    models.Reaction.post_id,
                    models.Reaction.emoji,
                    func.count(models.Reaction.id).label("count"),
                )
                .filter(models.Reaction.post_id.in_(bdr.post_ids))
                .group_by(models.Reaction.post_id, models.Reaction.emoji)
                .all()
            )

            post_id_to_sqid = {p.id: p.public_sqid for p in posts}
            reactions_by_post = {}

            for post_id, emoji, count in reactions:
                sqid_val = post_id_to_sqid.get(post_id)
                if sqid_val:
                    if sqid_val not in reactions_by_post:
                        reactions_by_post[sqid_val] = {}
                    reactions_by_post[sqid_val][emoji] = count

            reactions_data = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "reactions_by_artwork": reactions_by_post,
            }

        # Create ZIP file
        vault_base = Path(os.getenv("VAULT_LOCATION", "/vault"))
        bdr_dir = vault_base / "bdr" / user_sqid
        bdr_dir.mkdir(parents=True, exist_ok=True)

        zip_filename = f"{bdr_id}.zip"
        zip_path = bdr_dir / zip_filename

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            artworks_dir = tmpdir_path / "artworks"
            artworks_dir.mkdir()

            # Download and add artworks
            for post in posts:
                try:
                    # Determine file extension from native PostFile
                    native_pf = next((f for f in post.files if f.is_native), None)
                    native_fmt = native_pf.format if native_pf else "png"
                    ext = f".{native_fmt}"

                    artwork_filename = f"{post.public_sqid}{ext}"

                    # Get artwork file from vault using storage_key and storage_shard
                    if post.storage_key and native_pf:
                        source_path = vault.get_artwork_file_path(
                            post.storage_key,
                            vault.FORMAT_TO_EXT.get(native_fmt, f".{native_fmt}"),
                            storage_shard=post.storage_shard,
                        )
                        if source_path.exists():
                            shutil.copy(source_path, artworks_dir / artwork_filename)
                        else:
                            logger.warning(f"Vault file not found: {source_path}")
                            continue
                    else:
                        logger.warning(f"Cannot locate artwork for post {post.id}")
                        continue

                    # Add to metadata
                    metadata["artworks"].append(
                        {
                            "sqid": post.public_sqid,
                            "filename": artwork_filename,
                            "title": post.title,
                            "description": post.description,
                            "created_at": post.created_at.isoformat(),
                            "width": post.width,
                            "height": post.height,
                            "frame_count": post.frame_count,
                            "file_format": native_fmt,
                            "hashtags": post.hashtags or [],
                            "mod_hashtags": post.mod_hashtags or [],
                        }
                    )

                except Exception as e:
                    logger.error(f"Failed to process artwork {post.id}: {e}")
                    # Continue with other artworks

            # Write metadata.json
            (tmpdir_path / "metadata.json").write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False)
            )

            # Write comments.json if requested
            if comments_data:
                (tmpdir_path / "comments.json").write_text(
                    json.dumps(comments_data, indent=2, ensure_ascii=False)
                )

            # Write reactions.json if requested
            if reactions_data:
                (tmpdir_path / "reactions.json").write_text(
                    json.dumps(reactions_data, indent=2, ensure_ascii=False)
                )

            # Create ZIP
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Add artworks
                for artwork_file in artworks_dir.iterdir():
                    zf.write(artwork_file, f"artworks/{artwork_file.name}")

                # Add metadata
                zf.write(tmpdir_path / "metadata.json", "metadata.json")

                if comments_data:
                    zf.write(tmpdir_path / "comments.json", "comments.json")

                if reactions_data:
                    zf.write(tmpdir_path / "reactions.json", "reactions.json")

        # Update BDR record
        now = datetime.now(timezone.utc)
        bdr.status = "ready"
        bdr.file_path = f"bdr/{user_sqid}/{zip_filename}"
        bdr.file_size_bytes = zip_path.stat().st_size
        bdr.completed_at = now
        bdr.expires_at = now + timedelta(days=7)
        db.commit()

        # Send email notification if requested
        if bdr.send_email:
            try:
                from .services.email import send_bdr_ready_email

                send_bdr_ready_email(
                    to_email=user.email,
                    handle=user.handle,
                    artwork_count=len(posts),
                    download_url=f"{os.getenv('BASE_URL', 'https://makapix.club')}/u/{user_sqid}/posts?bdr={bdr_id}",
                    expires_at=bdr.expires_at,
                )
            except Exception as e:
                logger.error(f"Failed to send BDR email: {e}")
                # Don't fail the task if email fails

        logger.info(f"BDR {bdr_id} completed successfully")
        return {
            "status": "success",
            "bdr_id": bdr_id,
            "file_size": bdr.file_size_bytes,
        }

    except Exception as e:
        logger.error(f"Error processing BDR {bdr_id}: {e}", exc_info=True)

        # Update status to failed
        try:
            db.rollback()
            bdr = (
                db.query(models.BatchDownloadRequest)
                .filter(models.BatchDownloadRequest.id == UUID(bdr_id))
                .first()
            )
            if bdr:
                bdr.status = "failed"
                bdr.error_message = str(e)[:500]  # Truncate long errors
                bdr.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as update_error:
            logger.error(f"Failed to update BDR status: {update_error}")

        raise  # Re-raise for Celery retry

    finally:
        db.close()


@celery_app.task(name="app.tasks.cleanup_expired_bdrs", bind=True)
def cleanup_expired_bdrs(self) -> dict[str, Any]:
    """
    Daily task: Clean up expired Batch Download Requests.

    Actions:
    1. Find BDRs where status='ready' and expires_at < now
    2. Delete the ZIP file from vault
    3. Update status to 'expired'
    4. Purge stale BDR rows entirely (hard delete) once they are 2 weeks
       past their dead state: expired 2 weeks after expires_at, failed
       2 weeks after failure, and pending/processing rows stuck for 2+
       weeks (e.g. worker crash mid-job).

    Runs daily at 04:30 US Eastern (configured in beat_schedule).
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import and_, func, or_

    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        logger.info("Starting expired BDRs cleanup task")

        now = datetime.now(timezone.utc)
        vault_base = Path(os.getenv("VAULT_LOCATION", "/vault"))

        # Find expired BDRs
        expired_bdrs = (
            db.query(models.BatchDownloadRequest)
            .filter(
                models.BatchDownloadRequest.status == "ready",
                models.BatchDownloadRequest.expires_at < now,
            )
            .all()
        )

        cleaned_up = 0
        errors = []

        for bdr in expired_bdrs:
            try:
                # Delete ZIP file
                if bdr.file_path:
                    zip_path = vault_base / bdr.file_path
                    if zip_path.exists():
                        zip_path.unlink()
                        logger.info(f"Deleted BDR file: {zip_path}")

                # Update status
                bdr.status = "expired"
                bdr.file_path = None
                bdr.file_size_bytes = None
                cleaned_up += 1

            except Exception as e:
                logger.error(f"Error cleaning up BDR {bdr.id}: {e}")
                errors.append({"bdr_id": str(bdr.id), "error": str(e)})

        db.commit()

        # Purge stale BDR rows so they drop off the PMD list for good
        purge_cutoff = now - timedelta(days=14)
        stale_bdrs = (
            db.query(models.BatchDownloadRequest)
            .filter(
                or_(
                    and_(
                        models.BatchDownloadRequest.status == "expired",
                        models.BatchDownloadRequest.expires_at < purge_cutoff,
                    ),
                    and_(
                        models.BatchDownloadRequest.status == "failed",
                        func.coalesce(
                            models.BatchDownloadRequest.completed_at,
                            models.BatchDownloadRequest.created_at,
                        )
                        < purge_cutoff,
                    ),
                    and_(
                        models.BatchDownloadRequest.status.in_(
                            ["pending", "processing"]
                        ),
                        models.BatchDownloadRequest.created_at < purge_cutoff,
                    ),
                )
            )
            .all()
        )

        purged = 0
        for bdr in stale_bdrs:
            try:
                # Defensive: a stuck/failed row may still have a ZIP on disk
                if bdr.file_path:
                    zip_path = vault_base / bdr.file_path
                    if zip_path.exists():
                        zip_path.unlink()
                        logger.info(f"Deleted BDR file: {zip_path}")

                db.delete(bdr)
                purged += 1

            except Exception as e:
                logger.error(f"Error purging BDR {bdr.id}: {e}")
                errors.append({"bdr_id": str(bdr.id), "error": str(e)})

        db.commit()

        # Also clean up orphaned BDR directories (empty directories)
        bdr_base = vault_base / "bdr"
        if bdr_base.exists():
            for user_dir in bdr_base.iterdir():
                if user_dir.is_dir() and not any(user_dir.iterdir()):
                    try:
                        user_dir.rmdir()
                        logger.info(f"Removed empty BDR directory: {user_dir}")
                    except Exception as e:
                        logger.warning(
                            f"Failed to remove empty directory {user_dir}: {e}"
                        )

        logger.info(f"Cleaned up {cleaned_up} expired BDRs, purged {purged} stale BDRs")
        return {
            "status": "success",
            "cleaned_up": cleaned_up,
            "purged": purged,
            "errors": errors if errors else None,
        }

    except Exception as e:
        logger.error(f"Error in cleanup_expired_bdrs task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.renew_crl_if_needed", bind=True)
def renew_crl_if_needed(self) -> dict[str, Any]:
    """
    Renew the MQTT Certificate Revocation List (CRL) if it's approaching expiration.

    The CRL is used by Mosquitto to verify client certificates. If the CRL expires,
    all client connections will be rejected. This task proactively renews the CRL
    when it's within 7 days of expiration.

    Runs daily at 05:00 US Eastern (configured in beat_schedule).
    """
    from datetime import datetime, timedelta, timezone

    from .mqtt.crl_init import get_crl_expiration, renew_crl

    try:
        logger.info("Checking CRL expiration status")

        # Get current CRL expiration
        expiration = get_crl_expiration()

        if expiration is None:
            logger.warning("CRL not found or invalid, creating new one")
            new_expiration = renew_crl()
            if new_expiration:
                return {
                    "status": "success",
                    "action": "created",
                    "new_expiration": new_expiration.isoformat(),
                }
            else:
                return {"status": "error", "message": "Failed to create CRL"}

        # Check if CRL is within 7 days of expiration
        now = datetime.now(timezone.utc)
        days_until_expiry = (expiration - now).days

        logger.info(
            f"CRL expires in {days_until_expiry} days ({expiration.isoformat()})"
        )

        if days_until_expiry <= 7:
            logger.info("CRL is within 7 days of expiration, renewing...")
            new_expiration = renew_crl()
            if new_expiration:
                logger.info(
                    f"CRL renewed successfully, new expiration: {new_expiration.isoformat()}"
                )
                return {
                    "status": "success",
                    "action": "renewed",
                    "old_expiration": expiration.isoformat(),
                    "new_expiration": new_expiration.isoformat(),
                    "days_until_old_expiry": days_until_expiry,
                }
            else:
                logger.error("Failed to renew CRL")
                return {"status": "error", "message": "Failed to renew CRL"}
        else:
            return {
                "status": "success",
                "action": "none",
                "expiration": expiration.isoformat(),
                "days_until_expiry": days_until_expiry,
            }

    except Exception as e:
        logger.error(f"Error in renew_crl_if_needed task: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


# ============================================================================
# ACCOUNT DELETION TASK
# ============================================================================


@celery_app.task(
    name="app.tasks.delete_user_account",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def delete_user_account_task(self, user_id: int) -> dict[str, Any]:
    """Permanently delete a user account and all associated data.

    Thin wrapper around ``_purge_user_account`` — the deletion steps live in
    that helper so the unverified-account reaper can reuse the exact same
    (FK-complete) logic instead of its own partial copy.
    """
    from .db import SessionLocal

    db = SessionLocal()
    try:
        counts = _purge_user_account(db, user_id)
    except Exception as e:
        logger.error(f"Error deleting account for user {user_id}: {e}", exc_info=True)
        db.rollback()
        raise  # Re-raise to trigger Celery retry
    finally:
        db.close()

    logger.info(f"Account deletion completed for user {user_id}: {counts}")
    return {"status": "success", "user_id": user_id, "counts": counts}


def _purge_user_account(db: Session, user_id: int) -> dict[str, Any]:
    """Delete one user and every FK-dependent row, using the caller's session.

    Handles the complete deletion of a user account:
    1. Reactions - delete all user's reactions on posts
    2. Comments - special handling for hierarchy:
       - Comments WITH children: Set author_id=NULL, body="[deleted comment]"
       - Comments WITHOUT children: Hard delete
    3. Posts - delete all posts AND vault files
    4. Players - delete all registered physical players
    5. BatchDownloadRequests - delete records AND zip files from /vault/bdr/
    6. SocialNotifications - delete both received and actor notifications
    7. UserHighlights - delete profile highlights
    8. BadgeGrant & ReputationHistory - delete badges and rep history
    9. Follow - delete both follower_id and following_id relationships
    10. CategoryFollow - delete category follows
    11. BlogPostComment - same hierarchy handling as regular comments
    12. BlogPost - delete all blog posts
    13. Tokens - delete RefreshToken, EmailVerificationToken, PasswordResetToken
    14. AuthIdentity - delete OAuth identities
    15. Avatar - delete avatar file from vault
    15b. FK-blocking rows - audit_logs / admin_notes / violations /
         push_tokens (RESTRICT or NO ACTION, NOT NULL) are erased and
         reports.reporter_id is anonymized, or the final DELETE would fail
    16. User record - final delete (frees email for reuse)

    Commits progressively (so a large account doesn't balloon memory). Returns
    the per-table counts. On error rolls back and re-raises; the caller owns the
    session lifecycle (open/close) and decides whether to retry or skip.
    """
    from pathlib import Path
    from sqlalchemy import func
    from . import models
    from .vault import delete_all_artwork_formats, get_vault_location
    from .avatar_vault import try_delete_avatar_by_public_url

    counts = {
        "reactions": 0,
        "comments_deleted": 0,
        "comments_anonymized": 0,
        "posts": 0,
        "players": 0,
        "batch_download_requests": 0,
        "notifications": 0,
        "highlights": 0,
        "badges": 0,
        "reputation_history": 0,
        "follows": 0,
        "category_follows": 0,
        "blog_post_comments_deleted": 0,
        "blog_post_comments_anonymized": 0,
        "blog_posts": 0,
        "refresh_tokens": 0,
        "email_tokens": 0,
        "password_tokens": 0,
        "auth_identities": 0,
        "avatar_deleted": False,
    }

    try:
        logger.info(f"Starting account deletion for user {user_id}")

        # Get the user first
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            logger.error(f"User {user_id} not found for deletion")
            return {"status": "error", "message": "User not found"}

        # 1. Delete all user's reactions
        counts["reactions"] = (
            db.query(models.Reaction)
            .filter(models.Reaction.user_id == user_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info(f"Deleted {counts['reactions']} reactions for user {user_id}")

        # Also delete blog post reactions
        db.query(models.BlogPostReaction).filter(
            models.BlogPostReaction.user_id == user_id
        ).delete(synchronize_session=False)
        db.commit()

        # 2. Handle comments (special logic for hierarchical comments)
        # First, find comments WITH children - these need to be anonymized
        # Then, find comments WITHOUT children - these can be hard deleted

        # Get all comment IDs by this user
        user_comments = (
            db.query(models.Comment).filter(models.Comment.author_id == user_id).all()
        )

        for comment in user_comments:
            # Check if this comment has children
            has_children = (
                db.query(models.Comment)
                .filter(models.Comment.parent_id == comment.id)
                .count()
                > 0
            )

            if has_children:
                # Anonymize: set author_id=NULL and body to placeholder
                comment.author_id = None
                comment.body = "[deleted comment]"
                counts["comments_anonymized"] += 1
            else:
                # Hard delete
                db.delete(comment)
                counts["comments_deleted"] += 1

        db.commit()
        logger.info(
            f"Handled comments for user {user_id}: "
            f"{counts['comments_deleted']} deleted, {counts['comments_anonymized']} anonymized"
        )

        # 3. Delete all posts AND vault files
        user_posts = db.query(models.Post).filter(models.Post.owner_id == user_id).all()

        for post in user_posts:
            # Delete vault files for this post
            try:
                formats = [pf.format for pf in post.files]
                if formats:
                    delete_all_artwork_formats(
                        post.storage_key, formats, storage_shard=post.storage_shard
                    )
            except Exception as e:
                logger.warning(f"Failed to delete vault files for post {post.id}: {e}")

            # Attached .mkpx layers file, if any — independent of the
            # formats gate above, or account deletion would orphan it
            if post.storage_key and post.mkpx_file_bytes is not None:
                from .vault import delete_mkpx_from_vault

                delete_mkpx_from_vault(post.storage_key, post.storage_shard)

            # Delete the post (cascades to comments, reactions, admin_notes)
            db.delete(post)
            counts["posts"] += 1

            # Commit in batches to avoid memory issues
            if counts["posts"] % 50 == 0:
                db.commit()
                logger.info(f"Deleted {counts['posts']} posts so far...")

        db.commit()
        logger.info(f"Deleted {counts['posts']} posts for user {user_id}")

        # 4. Delete all players (per-player teardown so cert revocation,
        # MQTT password removal, and audit logging happen — bulk SQL delete
        # would bypass all of that).
        from .services.player_teardown import teardown_player

        players = (
            db.query(models.Player).filter(models.Player.owner_id == user_id).all()
        )
        for player in players:
            try:
                teardown_player(db, player, removed_by=user_id)
                counts["players"] += 1
            except Exception:
                logger.exception(
                    f"Failed to tear down player {player.id} for user {user_id}"
                )
                db.rollback()
        logger.info(f"Deleted {counts['players']} players for user {user_id}")

        # 5. Delete BatchDownloadRequests AND their zip files
        bdrs = (
            db.query(models.BatchDownloadRequest)
            .filter(models.BatchDownloadRequest.user_id == user_id)
            .all()
        )

        vault_base = get_vault_location()
        for bdr in bdrs:
            # Delete the zip file if it exists
            if bdr.file_path:
                try:
                    zip_path = vault_base / bdr.file_path.lstrip("/")
                    if zip_path.exists():
                        zip_path.unlink()
                        logger.info(f"Deleted BDR zip file: {zip_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete BDR zip file for {bdr.id}: {e}")

            db.delete(bdr)
            counts["batch_download_requests"] += 1

        db.commit()
        logger.info(
            f"Deleted {counts['batch_download_requests']} batch download requests for user {user_id}"
        )

        # 6. Delete SocialNotifications (both received and actor)
        counts["notifications"] = (
            db.query(models.SocialNotification)
            .filter(
                (models.SocialNotification.user_id == user_id)
                | (models.SocialNotification.actor_id == user_id)
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info(
            f"Deleted {counts['notifications']} notifications for user {user_id}"
        )

        # 7. Delete UserHighlights
        counts["highlights"] = (
            db.query(models.UserHighlight)
            .filter(models.UserHighlight.user_id == user_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info(f"Deleted {counts['highlights']} highlights for user {user_id}")

        # 8. Delete BadgeGrant and ReputationHistory
        counts["badges"] = (
            db.query(models.BadgeGrant)
            .filter(models.BadgeGrant.user_id == user_id)
            .delete(synchronize_session=False)
        )
        db.commit()

        counts["reputation_history"] = (
            db.query(models.ReputationHistory)
            .filter(models.ReputationHistory.user_id == user_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info(
            f"Deleted {counts['badges']} badges and {counts['reputation_history']} rep history for user {user_id}"
        )

        # 9. Delete Follow relationships (both directions)
        follows_as_follower = (
            db.query(models.Follow)
            .filter(models.Follow.follower_id == user_id)
            .delete(synchronize_session=False)
        )
        follows_as_following = (
            db.query(models.Follow)
            .filter(models.Follow.following_id == user_id)
            .delete(synchronize_session=False)
        )
        counts["follows"] = follows_as_follower + follows_as_following
        db.commit()
        logger.info(
            f"Deleted {counts['follows']} follow relationships for user {user_id}"
        )

        # 10. Delete CategoryFollow
        counts["category_follows"] = (
            db.query(models.CategoryFollow)
            .filter(models.CategoryFollow.user_id == user_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info(
            f"Deleted {counts['category_follows']} category follows for user {user_id}"
        )

        # 11. Handle BlogPostComments (same logic as regular comments)
        user_blog_comments = (
            db.query(models.BlogPostComment)
            .filter(models.BlogPostComment.author_id == user_id)
            .all()
        )

        for comment in user_blog_comments:
            has_children = (
                db.query(models.BlogPostComment)
                .filter(models.BlogPostComment.parent_id == comment.id)
                .count()
                > 0
            )

            if has_children:
                comment.author_id = None
                comment.body = "[deleted comment]"
                counts["blog_post_comments_anonymized"] += 1
            else:
                db.delete(comment)
                counts["blog_post_comments_deleted"] += 1

        db.commit()
        logger.info(
            f"Handled blog comments for user {user_id}: "
            f"{counts['blog_post_comments_deleted']} deleted, "
            f"{counts['blog_post_comments_anonymized']} anonymized"
        )

        # 12. Delete BlogPosts
        counts["blog_posts"] = (
            db.query(models.BlogPost)
            .filter(models.BlogPost.owner_id == user_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info(f"Deleted {counts['blog_posts']} blog posts for user {user_id}")

        # 13. Delete Tokens
        counts["refresh_tokens"] = (
            db.query(models.RefreshToken)
            .filter(models.RefreshToken.user_id == user_id)
            .delete(synchronize_session=False)
        )
        db.commit()

        counts["email_tokens"] = (
            db.query(models.EmailVerificationToken)
            .filter(models.EmailVerificationToken.user_id == user_id)
            .delete(synchronize_session=False)
        )
        db.commit()

        counts["password_tokens"] = (
            db.query(models.PasswordResetToken)
            .filter(models.PasswordResetToken.user_id == user_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info(
            f"Deleted tokens for user {user_id}: "
            f"{counts['refresh_tokens']} refresh, "
            f"{counts['email_tokens']} email, "
            f"{counts['password_tokens']} password"
        )

        # 14. Delete AuthIdentity
        counts["auth_identities"] = (
            db.query(models.AuthIdentity)
            .filter(models.AuthIdentity.user_id == user_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info(
            f"Deleted {counts['auth_identities']} auth identities for user {user_id}"
        )

        # 15. Delete avatar from vault
        if user.avatar_url:
            counts["avatar_deleted"] = try_delete_avatar_by_public_url(user.avatar_url)
            logger.info(
                f"Avatar deletion for user {user_id}: {counts['avatar_deleted']}"
            )

        # 15b. Clear rows that FK-block the final DELETE. These reference
        # users.id with ON DELETE RESTRICT / NO ACTION and NOT NULL, so unlike
        # the CASCADE/SET NULL tables above they are not cleaned up implicitly
        # and would abort the whole deletion (this is why deletion previously
        # never completed: request_account_deletion writes an audit_logs row
        # whose actor_id is this very user).
        #  - reports.reporter_id is RESTRICT but nullable -> anonymize (keep the
        #    report, drop the reporter PII), matching the reporter-IP policy.
        #  - audit_logs / admin_notes / violations / push_tokens are
        #    NOT NULL -> the rows are erased with the account.
        counts["reports_anonymized"] = (
            db.query(models.Report)
            .filter(models.Report.reporter_id == user_id)
            .update({models.Report.reporter_id: None}, synchronize_session=False)
        )
        counts["audit_logs"] = (
            db.query(models.AuditLog)
            .filter(models.AuditLog.actor_id == user_id)
            .delete(synchronize_session=False)
        )
        counts["admin_notes"] = (
            db.query(models.AdminNote)
            .filter(models.AdminNote.created_by == user_id)
            .delete(synchronize_session=False)
        )
        counts["violations"] = (
            db.query(models.Violation)
            .filter(
                (models.Violation.user_id == user_id)
                | (models.Violation.moderator_id == user_id)
            )
            .delete(synchronize_session=False)
        )
        counts["push_tokens"] = (
            db.query(models.PushToken)
            .filter(models.PushToken.user_id == user_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info(
            f"Cleared FK-blocking rows for user {user_id}: "
            f"{counts['audit_logs']} audit, {counts['admin_notes']} admin notes, "
            f"{counts['violations']} violations, "
            f"{counts['push_tokens']} push tokens, "
            f"{counts['reports_anonymized']} reports anonymized"
        )

        # 16. Finally, delete the user record
        db.delete(user)
        db.commit()
        logger.info(f"Deleted user record for user {user_id}")

        # Invalidate any cached stats
        try:
            from .services.user_profile_stats import invalidate_user_profile_stats_cache

            invalidate_user_profile_stats_cache(db, user_id)
        except Exception as e:
            logger.warning(f"Failed to invalidate stats cache for user {user_id}: {e}")

        return counts

    except Exception:
        db.rollback()
        raise


# ============================================================================
# BACKFILL POST_FILES
# ============================================================================


@celery_app.task(name="app.tasks.backfill_post_files")
def backfill_post_files(batch_size: int = 100) -> dict[str, Any]:
    """
    Backfill post_files table for converted format variants by scanning the vault.

    The Alembic migration already created native rows from the old posts columns.
    This task adds rows for all converted format variants that exist on disk.

    Rules:
    - Static (frame_count=1): check for png, gif, webp, bmp
    - Animated (frame_count>1): check for gif, webp
    """
    from . import models, vault
    from .db import get_session

    db = next(get_session())
    try:
        # Query posts that have a native PostFile row
        from sqlalchemy import exists

        posts = (
            db.query(models.Post)
            .filter(
                models.Post.kind == "artwork",
                models.Post.storage_key.isnot(None),
                exists().where(
                    models.PostFile.post_id == models.Post.id,
                    models.PostFile.is_native == True,
                ),
            )
            .all()
        )

        total = len(posts)
        created = 0
        skipped = 0
        errors = 0

        for i, post in enumerate(posts):
            try:
                existing_formats = {pf.format for pf in post.files}

                # Determine target formats
                if post.frame_count > 1:
                    target_formats = ["gif", "webp"]
                else:
                    target_formats = ["png", "gif", "webp", "bmp"]

                for fmt in target_formats:
                    if fmt in existing_formats:
                        skipped += 1
                        continue

                    # Check if file exists in vault
                    ext = vault.FORMAT_TO_EXT.get(fmt, f".{fmt}")
                    file_path = vault.get_artwork_file_path(
                        post.storage_key, ext, storage_shard=post.storage_shard
                    )

                    if file_path.exists():
                        file_size = file_path.stat().st_size
                        pf = models.PostFile(
                            post_id=post.id,
                            format=fmt,
                            file_bytes=file_size,
                            is_native=False,
                        )
                        db.add(pf)
                        created += 1
                    else:
                        skipped += 1

                # Commit in batches
                if (i + 1) % batch_size == 0:
                    db.commit()
                    logger.info(
                        f"Backfill progress: {i + 1}/{total} posts, "
                        f"{created} created, {skipped} skipped"
                    )

            except Exception as e:
                logger.error(f"Error backfilling post {post.id}: {e}")
                errors += 1

        db.commit()
        logger.info(
            f"Backfill completed: {total} posts, "
            f"{created} created, {skipped} skipped, {errors} errors"
        )

        return {
            "status": "success",
            "total_posts": total,
            "created": created,
            "skipped": skipped,
            "errors": errors,
        }

    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================================
# BACKFILL ANIMATION DURATIONS (message 0010)
# ============================================================================


@celery_app.task(name="app.tasks.backfill_animation_durations")
def backfill_animation_durations(batch_size: int = 100) -> dict[str, Any]:
    """
    Re-extract per-frame durations for animated artworks from their native
    vault files. Manual trigger, idempotent (recomputes every animated post).

    Fixes the historical NULL min/max_frame_duration_ms on animated WebP
    natives (durations were read after seek() but before load(), and the
    WebP plugin only populates them on load) and populates the new
    total_duration_ms column under the clamp policy pinned in message 0010.
    """
    from datetime import datetime, timezone

    from PIL import Image

    from . import models, vault
    from .amp.metadata_extraction import (
        collect_frame_durations,
        compute_total_duration_ms,
        _min_max_durations,
    )
    from .db import get_session

    db = next(get_session())
    try:
        posts = (
            db.query(models.Post)
            .filter(
                models.Post.kind == "artwork",
                models.Post.frame_count > 1,
                models.Post.storage_key.isnot(None),
                models.Post.storage_shard.isnot(None),
            )
            .all()
        )

        total = len(posts)
        updated = 0
        skipped = 0
        errors = 0

        for i, post in enumerate(posts):
            try:
                native_pf = next((f for f in post.files if f.is_native), None)
                if not native_pf:
                    logger.warning(f"Post {post.id}: no native file row, skipping")
                    skipped += 1
                    continue

                native_format = native_pf.format.lower()
                file_path = vault.get_artwork_file_path(
                    post.storage_key,
                    vault.FORMAT_TO_EXT.get(native_format, f".{native_format}"),
                    storage_shard=post.storage_shard,
                )
                if not file_path.exists():
                    logger.warning(f"Post {post.id}: vault file missing, skipping")
                    skipped += 1
                    continue

                with Image.open(file_path) as img:
                    frame_count = getattr(img, "n_frames", 1)
                    if frame_count != post.frame_count:
                        logger.warning(
                            f"Post {post.id}: file has {frame_count} frames, "
                            f"DB says {post.frame_count} (using file)"
                        )
                    durations = collect_frame_durations(img, frame_count)

                min_d, max_d = _min_max_durations(durations)
                total_d = compute_total_duration_ms(durations, frame_count)
                changed = (
                    post.min_frame_duration_ms,
                    post.max_frame_duration_ms,
                    post.total_duration_ms,
                ) != (min_d, max_d, total_d)
                if not changed:
                    skipped += 1
                    continue

                post.min_frame_duration_ms = min_d
                post.max_frame_duration_ms = max_d
                post.total_duration_ms = total_d
                # Metadata-cache consumers key on this timestamp; without the
                # bump they would never learn the corrected values.
                post.metadata_modified_at = datetime.now(timezone.utc)
                updated += 1

                if (i + 1) % batch_size == 0:
                    db.commit()
                    logger.info(
                        f"Duration backfill progress: {i + 1}/{total} posts, "
                        f"{updated} updated, {skipped} skipped, {errors} errors"
                    )

            except Exception as e:
                logger.error(f"Error backfilling durations for post {post.id}: {e}")
                errors += 1

        db.commit()
        logger.info(
            f"Duration backfill completed: {total} posts, "
            f"{updated} updated, {skipped} skipped, {errors} errors"
        )

        return {
            "status": "success",
            "total_posts": total,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
        }

    except Exception as e:
        logger.error(f"Duration backfill failed: {e}", exc_info=True)
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(name="app.tasks.rollup_download_stats", bind=True)
def rollup_download_stats(self, target_date_iso: str | None = None) -> dict[str, Any]:
    """Roll up the Caddy vault access log into download_stats_daily.

    By default targets yesterday (UTC). Pass `target_date_iso="YYYY-MM-DD"` to
    re-aggregate a specific date — the UPSERT in the service makes this safe
    to re-run.

    Runs daily at 03:00 US Eastern (configured in beat_schedule).
    """
    from datetime import date, datetime, timedelta, timezone

    from .services.download_stats import rollup_download_stats as _impl

    if target_date_iso:
        target_date = date.fromisoformat(target_date_iso)
    else:
        target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

    try:
        result = _impl(target_date)
        logger.info(f"rollup_download_stats({target_date}) -> {result}")
        return result
    except Exception as e:
        logger.error(f"rollup_download_stats failed: {e}", exc_info=True)
        raise


@celery_app.task(name="app.tasks.send_push_notification", bind=True)
def send_push_notification(self, user_id, notification_type, data=None):
    """Deliver a social notification as a mobile push (FCM). Best-effort.

    No-ops cleanly when push is not configured (see services/push.py).
    """
    from .db import SessionLocal
    from .services.push import send_push_to_user

    db = SessionLocal()
    try:
        sent = send_push_to_user(db, user_id, notification_type, data or {})
        if sent:
            logger.info(f"Sent {sent} push(es) to user {user_id} ({notification_type})")
        return sent
    except Exception as e:
        logger.error(f"send_push_notification failed: {e}", exc_info=True)
        return 0
    finally:
        db.close()
