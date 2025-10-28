"""Legacy endpoints for backwards compatibility."""

from __future__ import annotations

from fastapi import APIRouter, status

from .. import schemas
from ..tasks import hash_url

router = APIRouter(prefix="", tags=["Legacy"])


@router.post("/tasks/hash-url", response_model=schemas.HashUrlResponse, status_code=status.HTTP_202_ACCEPTED)
def enqueue_hash_url(payload: schemas.HashUrlRequest) -> schemas.HashUrlResponse:
    """
    Queue URL hashing task (legacy demo endpoint).
    
    TODO: Remove in production or move to /admin/tasks
    """
    result = hash_url.delay(str(payload.url))
    return schemas.HashUrlResponse(task_id=result.id)
