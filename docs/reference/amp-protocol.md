# Artwork Metadata Protocol (AMP)

Technical reference for filtering artwork by metadata.

## Overview

AMP (Artwork Metadata Protocol) provides a query language for filtering artwork based on technical metadata. It's used in MQTT `query_posts` requests to select artwork matching specific criteria.

## Filter Syntax

Each filter criterion has three parts:

```json
{
  "field": "width",
  "op": "gte",
  "value": 64
}
```

| Part | Description |
|------|-------------|
| `field` | Metadata field to filter on |
| `op` | Comparison operator |
| `value` | Value(s) to compare against |

Multiple criteria are combined with AND logic.

## Fields

### Numeric Fields

| Field | Type | Description |
|-------|------|-------------|
| `width` | integer | Image width in pixels (8-256) |
| `height` | integer | Image height in pixels (8-256) |
| `file_bytes` | integer | File size in bytes (per variant; combines with `file_format` on same variant) |
| `frame_count` | integer | Number of animation frames (1 for static) |
| `min_frame_duration_ms` | integer | Shortest frame duration (nullable) |
| `max_frame_duration_ms` | integer | Longest frame duration (nullable) |
| `unique_colors` | integer | Number of unique colors (nullable) |

### Boolean Fields

| Field | Type | Description |
|-------|------|-------------|
| `transparency_meta` | boolean | Has transparency (per file metadata) |
| `alpha_meta` | boolean | Has alpha channel (per file metadata) |
| `transparency_actual` | boolean | Has transparent pixels (analyzed) |
| `alpha_actual` | boolean | Has semi-transparent pixels (analyzed) |

### Enum Fields

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `file_format` | string | `png`, `gif`, `webp`, `bmp` | Matches any file variant (native or converted) |
| `native_file_format` | string | `png`, `gif`, `webp`, `bmp` | Matches native (original upload) format only |
| `kind` | string | `artwork`, `playlist` | Post type |

## Operators

### Comparison Operators

| Operator | Symbol | Description | Valid For |
|----------|--------|-------------|-----------|
| `eq` | = | Equal to | All fields |
| `neq` | != | Not equal to | All fields |
| `lt` | < | Less than | Numeric only |
| `gt` | > | Greater than | Numeric only |
| `lte` | <= | Less than or equal | Numeric only |
| `gte` | >= | Greater than or equal | Numeric only |

### Set Operators

| Operator | Description | Valid For |
|----------|-------------|-----------|
| `in` | Value in array | Numeric, Enum |
| `not_in` | Value not in array | Numeric, Enum |

### Null Operators

| Operator | Description | Valid For |
|----------|-------------|-----------|
| `is_null` | Field is null | Nullable fields only |
| `is_not_null` | Field is not null | Nullable fields only |

### Nullable Fields

Only these fields support `is_null`/`is_not_null`:

- `min_frame_duration_ms`
- `max_frame_duration_ms`
- `unique_colors`

## Operator Compatibility

| Field Type | Valid Operators |
|------------|-----------------|
| Numeric | `eq`, `neq`, `lt`, `gt`, `lte`, `gte`, `in`, `not_in`, `is_null`, `is_not_null` |
| Boolean | `eq`, `neq` |
| Enum | `eq`, `neq`, `in`, `not_in`, `is_null`, `is_not_null` |

## Examples

### Filter by Dimensions

64x64 artwork only:

```json
{
  "criteria": [
    {"field": "width", "op": "eq", "value": 64},
    {"field": "height", "op": "eq", "value": 64}
  ]
}
```

Minimum 32x32:

```json
{
  "criteria": [
    {"field": "width", "op": "gte", "value": 32},
    {"field": "height", "op": "gte", "value": 32}
  ]
}
```

### Filter Animations

Animated GIFs only:

```json
{
  "criteria": [
    {"field": "frame_count", "op": "gt", "value": 1},
    {"field": "file_format", "op": "eq", "value": "gif"}
  ]
}
```

Static images only:

```json
{
  "criteria": [
    {"field": "frame_count", "op": "eq", "value": 1}
  ]
}
```

### Filter by Format

PNG or WebP variant available:

```json
{
  "criteria": [
    {"field": "file_format", "op": "in", "value": ["png", "webp"]}
  ]
}
```

### Filter by Native Format

Posts originally uploaded as GIF:

```json
{
  "criteria": [
    {"field": "native_file_format", "op": "eq", "value": "gif"}
  ]
}
```

`file_format` matches any variant (native or server-converted). `native_file_format` matches only the original upload format. A WebP-native post with a GIF conversion matches `file_format = "gif"` but not `native_file_format = "gif"`.

They can be combined: find WebP-native posts that have a BMP variant:

```json
{
  "criteria": [
    {"field": "native_file_format", "op": "eq", "value": "webp"},
    {"field": "file_format", "op": "eq", "value": "bmp"}
  ]
}
```

### Filter Transparency

Images with actual transparent pixels:

```json
{
  "criteria": [
    {"field": "transparency_actual", "op": "eq", "value": true}
  ]
}
```

Images without alpha (for LED displays):

```json
{
  "criteria": [
    {"field": "alpha_actual", "op": "eq", "value": false}
  ]
}
```

### Filter by File Size

Under 10KB:

```json
{
  "criteria": [
    {"field": "file_bytes", "op": "lt", "value": 10240}
  ]
}
```

### Filter by Color Count

Low color count (8-bit palette friendly):

```json
{
  "criteria": [
    {"field": "unique_colors", "op": "is_not_null"},
    {"field": "unique_colors", "op": "lte", "value": 256}
  ]
}
```

### Combined Example

64x64 static PNG with low color count:

```json
{
  "criteria": [
    {"field": "width", "op": "eq", "value": 64},
    {"field": "height", "op": "eq", "value": 64},
    {"field": "frame_count", "op": "eq", "value": 1},
    {"field": "file_format", "op": "eq", "value": "png"},
    {"field": "unique_colors", "op": "lte", "value": 64}
  ]
}
```

## Complete Request Example

Full `query_posts` request with AMP filtering:

```json
{
  "request_type": "query_posts",
  "request_id": "req-001",
  "channel": "promoted",
  "limit": 10,
  "criteria": [
    {"field": "width", "op": "gte", "value": 64},
    {"field": "height", "op": "gte", "value": 64},
    {"field": "frame_count", "op": "eq", "value": 1}
  ],
  "include_fields": ["id", "art_url", "width", "height", "unique_colors"]
}
```

## Error Handling

Invalid filter criteria return errors:

```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR",
  "message": "Operator 'lt' not valid for boolean field 'transparency_actual'"
}
```

Common validation errors:

| Error | Cause |
|-------|-------|
| Invalid operator for field type | Using `lt` on boolean field |
| Field is not nullable | Using `is_null` on non-nullable field |
| Invalid value type | String value for numeric field |
| Unknown field | Misspelled field name |

## Best Practices

1. **Start broad, then narrow** - Add criteria incrementally to avoid empty results
2. **Check nullable fields** - Use `is_not_null` before comparing nullable fields
3. **Combine for device constraints** - Match your display's capabilities (dimensions, color depth)
4. **Use `in` for multiple values** - More efficient than multiple `eq` criteria
