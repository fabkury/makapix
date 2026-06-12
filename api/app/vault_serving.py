"""Serving-layer fallback for legacy 3-level vault URLs.

Legacy 3-level URLs stay valid permanently at the serving layer
(docs/vault-resharding/DECISIONS.md D16): when a request path has the
3-level shape and no file exists there, the response is served from the
asset's 2-level location — same response, no redirect. While a legacy twin
copy exists on disk it is served as-is; the remap only fires on a miss.

The mapping needs no hashing and no DB access: the first two components of
a 3-level shard are the first two SHA-256 digest bytes hex-rendered, and
the 2-level shard is those same bytes masked to their low 6 bits
(``vault.compute_storage_shard_v2``). Masking a byte with 0x3F keeps the
low nibble and reduces the high nibble to its low 2 bits, so per component
only the first hex character changes: ``c -> c & 0x3``.

The Caddy vault-subdomain site blocks implement the same miss-only remap
(deploy/stack/caddy/Caddyfile.global); keep the two in sync.
"""

from __future__ import annotations

import os
import re

from starlette.staticfiles import StaticFiles

# 3-level-shaped relative path: optional avatar/ prefix, three 2-hex-char
# shard components, then a filename (no deeper nesting). StaticFiles passes
# the path without a leading slash.
_LEGACY_PATH_RE = re.compile(
    r"^(?P<prefix>avatar/)?"
    r"(?P<h1>[0-9a-f]{2})/(?P<h2>[0-9a-f]{2})/[0-9a-f]{2}/"
    r"(?P<name>[^/]+)$"
)


def legacy_vault_path_to_v2(path: str) -> str | None:
    """Map a legacy 3-level vault path to its 2-level equivalent.

    Returns None if the path is not 3-level-shaped. Pure string transform;
    see module docstring for why no hashing is needed.
    """
    m = _LEGACY_PATH_RE.match(path)
    if m is None:
        return None
    a = int(m["h1"], 16) & 0x3F
    b = int(m["h2"], 16) & 0x3F
    return f"{m['prefix'] or ''}{a:02x}/{b:02x}/{m['name']}"


class LegacyShardFallbackStaticFiles(StaticFiles):
    """StaticFiles that retries missing 3-level paths at the 2-level twin."""

    def lookup_path(self, path: str) -> tuple[str, os.stat_result | None]:
        full_path, stat_result = super().lookup_path(path)
        if stat_result is None:
            v2_path = legacy_vault_path_to_v2(path)
            if v2_path is not None:
                return super().lookup_path(v2_path)
        return full_path, stat_result
