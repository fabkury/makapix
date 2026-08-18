"""CacheJSONEncoder must serialize the payloads callers actually cache —
pydantic `model_dump()` dicts, which keep UUID and datetime objects.
Regression: datetimes used to raise "Object of type datetime is not JSON
serializable", so cache writes (e.g. feed:recent) silently failed and the
endpoint served uncached on every request.
"""

import json
import uuid
from datetime import date, datetime, timezone

from app.cache import CacheJSONEncoder


def test_encodes_uuid_and_datetime():
    payload = {
        "storage_key": uuid.uuid4(),
        "created_at": datetime(2026, 8, 18, 12, 0, 0, tzinfo=timezone.utc),
        "day": date(2026, 8, 18),
        "items": [{"nested_at": datetime(2026, 1, 1)}],
    }
    out = json.loads(json.dumps(payload, cls=CacheJSONEncoder))
    assert out["storage_key"] == str(payload["storage_key"])
    assert out["created_at"] == "2026-08-18T12:00:00+00:00"
    assert out["day"] == "2026-08-18"
    assert out["items"][0]["nested_at"] == "2026-01-01T00:00:00"


def test_datetime_roundtrips_through_pydantic():
    # Cache reads rebuild schemas from the JSON (schemas.Page(**cached)):
    # the ISO string must parse back into the schema's datetime field.
    from pydantic import BaseModel

    class M(BaseModel):
        created_at: datetime

    original = M(created_at=datetime(2026, 8, 18, 12, 0, 0, tzinfo=timezone.utc))
    cached = json.loads(json.dumps(original.model_dump(), cls=CacheJSONEncoder))
    assert M(**cached).created_at == original.created_at
