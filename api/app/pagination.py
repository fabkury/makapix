from __future__ import annotations

import base64
import json
from typing import Any

# TODO: Implement cursor-based pagination
# Cursor format: base64-encoded JSON with {id: last_record_id, sort: sort_field_value}
# This allows efficient pagination without OFFSET (which is slow for large datasets)


def encode_cursor(last_id: str, sort_value: Any = None) -> str:
    """
    Encode a pagination cursor from the last record's ID and sort value.

    PLACEHOLDER: Currently just base64-encodes the ID.

    TODO: Production implementation should:
    1. Create a dict with {id: last_id, sort: sort_value}
    2. JSON-encode the dict
    3. Base64-encode the JSON
    4. Return the encoded string

    Example:
        cursor = encode_cursor("abc-123", 1698765432)
        # Returns: eyJpZCI6ImFiYy0xMjMiLCJzb3J0IjoxNjk4NzY1NDMyfQ==

    Args:
        last_id: The ID of the last record in the current page
        sort_value: The sort field value of the last record (e.g., created_at timestamp)

    Returns:
        Base64-encoded cursor string
    """
    cursor_data = {"id": last_id}
    if sort_value is not None:
        cursor_data["sort"] = sort_value

    json_str = json.dumps(cursor_data, default=str)
    encoded = base64.b64encode(json_str.encode()).decode()
    return encoded


def decode_cursor(cursor: str | None) -> tuple[str, Any] | None:
    """
    Decode a pagination cursor to extract the last record's ID and sort value.

    PLACEHOLDER: Currently just base64-decodes and extracts ID.

    TODO: Production implementation should:
    1. Base64-decode the cursor string
    2. JSON-decode to get the dict
    3. Extract id and sort values
    4. Return tuple (id, sort_value)
    5. Handle invalid cursors gracefully

    Args:
        cursor: Base64-encoded cursor string, or None

    Returns:
        Tuple of (last_id, sort_value) if cursor is valid, None otherwise
    """
    if not cursor:
        return None

    try:
        decoded = base64.b64decode(cursor.encode()).decode()
        cursor_data = json.loads(decoded)
        last_id = cursor_data.get("id")
        sort_value = cursor_data.get("sort")

        if not last_id:
            return None

        return (last_id, sort_value)
    except (ValueError, KeyError, json.JSONDecodeError):
        # Invalid cursor format
        return None


def apply_cursor_filter(
    query,
    model_class,
    cursor: str | None,
    sort_field: str = "created_at",
    sort_desc: bool = True,
):
    """
    Apply cursor-based filtering to a SQLAlchemy query.

    Args:
        query: SQLAlchemy query object
        model_class: The model class being queried
        cursor: Pagination cursor string
        sort_field: Field name to sort by (default: created_at)
        sort_desc: Whether sorting is descending (default: True)

    Returns:
        Modified query with cursor filter applied
    """
    if not cursor:
        return query

    cursor_data = decode_cursor(cursor)
    if not cursor_data:
        return query

    last_id, sort_value = cursor_data
    sort_column = getattr(model_class, sort_field)
    id_column = model_class.id

    # Coerce cursor id to the model's id Python type (e.g., int for posts.id).
    # Without this, PostgreSQL may compare mismatched types (e.g., integer < varchar),
    # causing 500s during pagination.
    try:
        id_python_type = id_column.type.python_type  # type: ignore[attr-defined]
    except Exception:
        id_python_type = None

    if id_python_type is int and isinstance(last_id, str):
        try:
            last_id = int(last_id)
        except ValueError:
            # Invalid cursor; ignore it rather than failing the request
            return query
    elif id_python_type is not None and isinstance(last_id, str):
        # Best-effort coercion for other id types (UUID, etc.)
        try:
            last_id = id_python_type(last_id)  # type: ignore[misc]
        except Exception:
            return query

    # Cast sort_value to appropriate type based on sort_field
    if sort_field == "created_at":
        # Parse ISO format datetime string to Python datetime object
        from datetime import datetime

        if isinstance(sort_value, str):
            try:
                # Handle both 'Z' suffix and timezone offsets
                if sort_value.endswith("Z"):
                    sort_value = sort_value[:-1] + "+00:00"
                parsed_datetime = datetime.fromisoformat(sort_value)
                sort_value = parsed_datetime
            except (ValueError, AttributeError):
                # If parsing fails, return query without cursor filter
                return query

    if sort_desc:
        # For descending sort: (sort_field, id) < (sort_value, last_id)
        query = query.filter(
            (sort_column < sort_value)
            | ((sort_column == sort_value) & (id_column < last_id))
        )
    else:
        # For ascending sort: (sort_field, id) > (sort_value, last_id)
        query = query.filter(
            (sort_column > sort_value)
            | ((sort_column == sort_value) & (id_column > last_id))
        )

    return query


def create_page_response(
    items: list, limit: int, cursor: str | None = None, sort_field: str = "created_at"
) -> dict[str, Any]:
    """
    Create a paginated response with next cursor.

    Args:
        items: List of items for current page
        limit: Maximum number of items per page
        cursor: Current cursor (for debugging)
        sort_field: Field name used for sorting (default: created_at)

    Returns:
        Dict with items and next_cursor
    """
    next_cursor = None

    if len(items) > limit:
        # We fetched one extra item to check if there's a next page
        items = items[:limit]
        if items:
            last_item = items[-1]
            # Create cursor from the last item
            # Use the sort_field to determine what value to encode
            if sort_field == "created_at" and hasattr(last_item, "created_at"):
                next_cursor = encode_cursor(
                    str(last_item.id), last_item.created_at.isoformat()
                )
            elif sort_field == "handle" and hasattr(last_item, "handle"):
                next_cursor = encode_cursor(str(last_item.id), last_item.handle)
            else:
                # Fallback to ID only
                next_cursor = encode_cursor(str(last_item.id))

    return {"items": items, "next_cursor": next_cursor}
