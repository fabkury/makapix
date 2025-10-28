from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

import requests
from celery import Celery

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
    task_routes={"app.tasks.hash_url": {"queue": "default"}},
)

MAX_BYTES = 1_000_000


@celery_app.task(name="app.tasks.hash_url", bind=True)
def hash_url(self, url: str) -> dict[str, Any]:
    logger.info("Hashing URL %s", url)
    response = requests.get(url, stream=True, timeout=(3, 10))
    response.raise_for_status()

    total_bytes = 0
    digest = hashlib.sha256()

    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            total_bytes += len(chunk)
            if total_bytes > MAX_BYTES:
                raise ValueError("Content too large (limit 1MB for dev).")
            digest.update(chunk)

    result = {
        "url": url,
        "content_length": total_bytes,
        "sha256": digest.hexdigest(),
    }
    logger.info("Hash computed for %s (%s bytes)", url, total_bytes)
    return result
