#!/usr/bin/env python3
"""
Legacy frame_count Repair Script

Posts uploaded before frame-count metadata extraction landed (2025-12-04,
commit 683b627) were stored with the column default frame_count=1 even when
the native file is animated. SSAFPP trusts Post.frame_count, so those posts
got single-frame derived variants (png/gif/bmp) and a single-frame upscale.
Known affected prod posts: 1, 4, 5, 6, 7, 10 (survey 2026-08-18; the
2026-01 AMP backfill deliberately did not touch frame_count).

For each affected post this script:
  1. Re-runs the AMP inspector on the native file (sha256 must match
     Post.hash — aborts the post otherwise).
  2. Updates frame_count and the duration fields from the fresh metadata.
  3. Deletes the stale non-native variant files (canonical + twin) plus the
     upscaled file, and their PostFile rows.
  4. Enqueues process_ssafpp to regenerate the animated variants + upscale.

Usage (from within the API container):
    python /workspace/api/scripts/fix_legacy_frame_count.py --scan
    python /workspace/api/scripts/fix_legacy_frame_count.py --fix 1 4 5 6 7 10 --dry-run
    python /workspace/api/scripts/fix_legacy_frame_count.py --fix 1 4 5 6 7 10
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

sys.path.insert(0, "/workspace/api")

from PIL import Image

from app import vault
from app.db import SessionLocal
from app.models import Post, PostFile
from app.vault import FORMAT_TO_EXT


def native_file_path(post: Post, native_pf: PostFile) -> Path:
    fmt = native_pf.format.lower()
    return vault.get_artwork_file_path(
        post.storage_key,
        FORMAT_TO_EXT.get(fmt, f".{fmt}"),
        storage_shard=post.storage_shard,
    )


def run_amp_inspector(file_path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", "app.amp.amp_inspector", "--backend", str(file_path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": {
                "code": "SUBPROCESS_ERROR",
                "message": f"exit {result.returncode}: {result.stderr[:500]}",
            },
        }


def scan(db) -> list[int]:
    """List artwork posts whose static/animated classification disagrees
    with the native file on disk."""
    mismatched = []
    posts = (
        db.query(Post)
        .filter(Post.kind == "artwork", Post.storage_key.isnot(None))
        .order_by(Post.id)
        .all()
    )
    checked = 0
    for post in posts:
        native_pf = next((f for f in post.files if f.is_native), None)
        if native_pf is None:
            logger.warning(f"Post {post.id}: no native PostFile row, skipping")
            continue
        path = native_file_path(post, native_pf)
        if not path.exists():
            logger.warning(f"Post {post.id}: native file missing: {path}")
            continue
        checked += 1
        try:
            with Image.open(path) as img:
                actual = getattr(img, "n_frames", 1)
        except Exception as e:
            logger.warning(f"Post {post.id}: cannot open {path}: {e}")
            continue
        if (post.frame_count > 1) != (actual > 1):
            logger.info(
                f"Post {post.id}: MISMATCH db frame_count={post.frame_count}, "
                f"native {native_pf.format} has {actual} frames"
            )
            mismatched.append(post.id)
    logger.info(f"Scanned {checked} posts; {len(mismatched)} mismatched: {mismatched}")
    return mismatched


def fix_post(db, post_id: int, dry_run: bool) -> bool:
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None or post.kind != "artwork":
        logger.error(f"Post {post_id}: not found or not an artwork")
        return False

    native_pf = next((f for f in post.files if f.is_native), None)
    if native_pf is None:
        logger.error(f"Post {post_id}: no native PostFile row")
        return False

    path = native_file_path(post, native_pf)
    if not path.exists():
        logger.error(f"Post {post_id}: native file missing: {path}")
        return False

    result = run_amp_inspector(path)
    if not result.get("success"):
        err = result.get("error", {})
        logger.error(
            f"Post {post_id}: AMP inspection failed: "
            f"{err.get('code')}: {err.get('message')}"
        )
        return False
    metadata = result["metadata"]

    # The native file must be the file the post describes.
    if post.hash and metadata.get("sha256") != post.hash:
        logger.error(
            f"Post {post_id}: sha256 mismatch (db {post.hash}, "
            f"file {metadata.get('sha256')}) — aborting this post"
        )
        return False
    if (post.width, post.height) != (metadata["width"], metadata["height"]):
        logger.error(
            f"Post {post_id}: dimension mismatch "
            f"(db {post.width}x{post.height}, "
            f"file {metadata['width']}x{metadata['height']}) — aborting this post"
        )
        return False

    new_frame_count = metadata["frame_count"]
    if new_frame_count == post.frame_count:
        logger.info(f"Post {post_id}: frame_count already {new_frame_count}, skipping")
        return True

    stale_pfs = [f for f in post.files if not f.is_native]
    stale_formats = [f.format for f in stale_pfs]
    logger.info(
        f"Post {post_id}: frame_count {post.frame_count} -> {new_frame_count}, "
        f"durations min={metadata.get('shortest_duration_ms')} "
        f"max={metadata.get('longest_duration_ms')} "
        f"total={metadata.get('total_duration_ms')}; "
        f"deleting stale variants {stale_formats} + upscaled; re-running SSAFPP"
    )
    if dry_run:
        logger.info(f"  [DRY-RUN] Post {post_id}: no changes made")
        return True

    post.frame_count = new_frame_count
    post.min_frame_duration_ms = metadata.get("shortest_duration_ms")
    post.max_frame_duration_ms = metadata.get("longest_duration_ms")
    post.total_duration_ms = metadata.get("total_duration_ms")

    # Stale single-frame variants: files first (canonical + twin + upscaled),
    # then rows. delete_all_artwork_formats never touches formats not listed,
    # so the native file is safe.
    deletion = vault.delete_all_artwork_formats(
        post.storage_key, stale_formats, storage_shard=post.storage_shard
    )
    logger.info(f"Post {post_id}: vault deletion results: {deletion}")
    for pf in stale_pfs:
        db.delete(pf)

    db.commit()

    from app.tasks import process_ssafpp

    async_result = process_ssafpp.delay(post.id)
    logger.info(f"Post {post_id}: enqueued SSAFPP (task id {async_result.id})")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Repair legacy posts whose frame_count disagrees with the native file"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--scan",
        action="store_true",
        help="Report mismatched posts without changing anything",
    )
    group.add_argument(
        "--fix", type=int, nargs="+", metavar="POST_ID", help="Post IDs to repair"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview --fix without making changes"
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.scan:
            scan(db)
            return
        if args.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
        ok = failed = 0
        for post_id in args.fix:
            if fix_post(db, post_id, dry_run=args.dry_run):
                ok += 1
            else:
                failed += 1
                db.rollback()
        logger.info(f"Done: {ok} ok, {failed} failed")
        if failed:
            raise SystemExit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
