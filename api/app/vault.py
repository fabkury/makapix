"""Vault storage utility for artwork images.

The vault stores artwork images using a hash-based folder structure
derived from the artwork ID to ensure no single folder has too many files.

Sharding schemes (see docs/vault-resharding/):
    v1 (legacy, 3-level): VAULT_LOCATION/a4/47/ee/<storage_key>.png
        where "a4/47/ee" is the first 6 hex chars of sha256(str(storage_key))
        split into three 2-char components.
    v2 (target, 2-level):  VAULT_LOCATION/24/07/<storage_key>.png
        where each component is the low 6 bits of one of the first two
        sha256 digest bytes, rendered as 2 hex chars ("00".."3f").

The stored ``posts.storage_shard`` value is the single source of truth for
an artwork's canonical location and is treated as an opaque relative path
("aa/bb/cc" = v1, "aa/bb" = v2). During the resharding dual-location window
(migration Phases 0-5) writes and deletes in this module also touch the
*twin* location — the same key's path under the other scheme — per the
asset-level rule in ``should_mirror_to_twin``, so legacy assets' two copies
never diverge while v2-born assets stay single-copy. Dual-location logic
lives only in these primitives, never at call sites.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from uuid import UUID

from .settings import (
    MAKAPIX_ARTWORK_SIZE_LIMIT_BYTES,
    MAKAPIX_MKPX_SIZE_LIMIT_BYTES,
    MAKAPIX_VAULT_MIN_FREE_BYTES,
    vault_public_base_url,
)

logger = logging.getLogger(__name__)

# Maximum file size for artwork assets (bytes)
MAX_FILE_SIZE_BYTES = MAKAPIX_ARTWORK_SIZE_LIMIT_BYTES

# --- .mkpx layers-file attachments (docs/mkpx-upload/) -----------------------
# Stored under a sibling namespace {vault}/mkpx/{storage_shard}/{key}.mkpx,
# outside the artwork/avatar trees (no resharding dual-write involvement).
# The mkpx/ prefix must never be publicly served: Caddyfile.global 404s
# /mkpx/* on the vault subdomains (the only public vault serving surface).
MKPX_SUBDIR = "mkpx"
MKPX_EXTENSION = ".mkpx"
MKPX_MIME = "application/x-mkpx"
MKPX_SIZE_LIMIT_BYTES = MAKAPIX_MKPX_SIZE_LIMIT_BYTES
# 8-byte signatures (mkpx format spec): plain "‰MKPX\r\n\x1a" and the
# DEFLATE-compressed compact profile "‰MKPZ\r\n\x1a". Both accepted; the
# server never inspects past these bytes (opaque blob).
MKPX_MAGIC_PLAIN = b"\x89MKPX\x0d\x0a\x1a"
MKPX_MAGIC_COMPACT = b"\x89MKPZ\x0d\x0a\x1a"


class VaultFullError(OSError):
    """Vault volume is below the configured free-space floor."""


# Maximum canvas dimensions: 256x256
MAX_CANVAS_SIZE = 256

# Free-form band: from FREE_FORM_MIN_SIZE x FREE_FORM_MIN_SIZE up to
# MAX_CANVAS_SIZE x MAX_CANVAS_SIZE (inclusive), any width/height is allowed.
FREE_FORM_MIN_SIZE = 128

# Allowed sizes for canvases below the free-form band (i.e. with at least one
# dimension < 128). Both 90-degree orientations are listed explicitly. This is
# the single source of truth: `validate_image_dimensions` and the public
# `/config` upload block both read from it, so the rules can never drift.
ALLOWED_SMALL_DIMENSIONS: list[tuple[int, int]] = [
    (8, 8),
    (8, 16),
    (16, 8),
    (8, 32),
    (32, 8),
    (16, 16),
    (16, 32),
    (32, 16),
    (32, 32),
    (32, 64),
    (64, 32),
    (64, 64),
    (64, 128),
    (128, 64),
]

# Temp-file suffix for atomic writes. The reshard tooling's `status` ignores
# (but reports) these, and `clean-tmp` removes strays after a crash.
TMP_SUFFIX = ".reshard-tmp"

# Shard string lengths, used to tell the schemes apart ("aa/bb/cc" vs "aa/bb").
SHARD_V1_LEN = 8
SHARD_V2_LEN = 5

# File format to extension mapping
FORMAT_TO_EXT = {
    "png": ".png",
    "gif": ".gif",
    "webp": ".webp",
    "bmp": ".bmp",
}

# File format to MIME type mapping (for content-type headers)
FORMAT_TO_MIME = {
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "bmp": "image/bmp",
}

# Legacy: Allowed MIME types for upload validation (until frontend migrates)
ALLOWED_MIME_TYPES = {
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/x-ms-bmp": ".bmp",  # Alternative MIME type for BMP
}


def get_vault_location() -> Path:
    """Get the vault location from environment variable."""
    vault_path = os.environ.get("VAULT_LOCATION")
    if not vault_path:
        raise ValueError("VAULT_LOCATION environment variable is not set")
    return Path(vault_path)


def hash_artwork_id(artwork_id: UUID) -> str:
    """Hash the artwork ID using SHA256 for folder structure derivation."""
    return hashlib.sha256(str(artwork_id).encode()).hexdigest()


def compute_storage_shard_v1(storage_key: UUID) -> str:
    """
    Legacy 3-level shard: "a4/47/ee" (first 6 hex chars of SHA-256, split
    into 2-char components). Only the reshard tooling and the dual-location
    twin derivation should need to call this explicitly.
    """
    hash_value = hash_artwork_id(storage_key)
    return f"{hash_value[0:2]}/{hash_value[2:4]}/{hash_value[4:6]}"


def compute_storage_shard_v2(storage_key: UUID) -> str:
    """
    2-level shard: "24/07" — the low 6 bits of each of the first two SHA-256
    digest bytes, rendered as zero-padded hex ("00".."3f"). 64*64 = 4096
    shards.
    """
    digest = hashlib.sha256(str(storage_key).encode()).digest()
    return f"{digest[0] & 0x3F:02x}/{digest[1] & 0x3F:02x}"


def compute_storage_shard(storage_key: UUID) -> str:
    """
    Compute the canonical storage shard for a NEW artwork. Call ONCE at post
    creation; the value is persisted in posts.storage_shard and treated as
    opaque afterwards.

    v2 (2-level) since migration Phase 0 PR-B
    (docs/vault-resharding/PLAN.md §9). Existing rows keep their stored v1
    shards until the Phase 3 flip.
    """
    return compute_storage_shard_v2(storage_key)


def derive_twin_shard(storage_key: UUID, storage_shard: str) -> str:
    """
    Given a key's canonical shard, return the same key's shard under the
    *other* scheme. Used by the dual-location write/delete primitives during
    the resharding window.
    """
    if len(storage_shard) == SHARD_V1_LEN:
        return compute_storage_shard_v2(storage_key)
    if len(storage_shard) == SHARD_V2_LEN:
        return compute_storage_shard_v1(storage_key)
    raise ValueError(f"Unrecognized storage_shard format: {storage_shard!r}")


def _require_shard(storage_shard: str | None) -> str:
    """
    Validate that a stored shard was provided. Paths are never silently
    derived from the key: the stored shard is the source of truth, and a
    derived path can point at the wrong sharding scheme for this row.
    """
    if not storage_shard:
        raise ValueError(
            "storage_shard is required (it is the source of truth for the "
            "artwork's vault location); refusing to derive a path from the key"
        )
    return storage_shard


def get_artwork_folder_path(artwork_id: UUID, storage_shard: str) -> Path:
    """
    Get the folder path for an artwork from its stored shard.

    Args:
        artwork_id: The UUID of the artwork (unused for path construction,
                    kept for signature stability and error context)
        storage_shard: The stored shard path (e.g. "8c/4f/2a" or "8c/4f")
    """
    shard = _require_shard(storage_shard)
    return get_vault_location() / Path(shard)


def get_artwork_file_path(artwork_id: UUID, extension: str, storage_shard: str) -> Path:
    """
    Get the full file path for an artwork.

    Args:
        artwork_id: The UUID of the artwork
        extension: The file extension (e.g., ".png", ".jpg", ".gif")
        storage_shard: The stored shard path (required)

    Returns:
        Full path where the artwork file should be stored
    """
    folder_path = get_artwork_folder_path(artwork_id, storage_shard)
    # Ensure extension is lowercase and starts with a dot
    ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
    return folder_path / f"{artwork_id}{ext}"


def write_file_atomic(file_path: Path, content: bytes) -> None:
    """
    Write bytes to ``file_path`` atomically: temp file in the destination
    directory, fsync, then rename. Readers (Caddy / StaticFiles) never see a
    torn file.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = file_path.with_name(f"{file_path.name}.{os.getpid()}{TMP_SUFFIX}")
    try:
        with open(tmp_path, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, file_path)
    except OSError:
        # Best-effort cleanup; stray temp files are also handled by the
        # reshard tooling's clean-tmp.
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def get_vault_free_bytes() -> int:
    """Free bytes on the vault volume (statvfs)."""
    st = os.statvfs(get_vault_location())
    return st.f_bavail * st.f_frsize


def ensure_vault_headroom(incoming_bytes: int = 0) -> None:
    """
    Refuse writes that would drop the vault volume below the configured
    free-space floor (MAKAPIX_VAULT_MIN_FREE_BYTES). A clean, observable
    refusal beats ENOSPC halfway through a write.

    Raises:
        VaultFullError: if free space minus the incoming payload is below
            the floor.
    """
    free = get_vault_free_bytes()
    if free - incoming_bytes < MAKAPIX_VAULT_MIN_FREE_BYTES:
        raise VaultFullError(
            f"Vault below free-space floor: {free} bytes free, "
            f"{incoming_bytes} incoming, floor {MAKAPIX_VAULT_MIN_FREE_BYTES}"
        )


def write_stream_atomic(file_path: Path, source, expected_bytes: int) -> int:
    """
    Stream-copy ``source`` (a binary file object positioned at 0) to
    ``file_path`` atomically in 1 MiB chunks — never holds the payload in
    memory. Returns the byte count written; raises ValueError if it differs
    from ``expected_bytes`` (truncated/oversized stream).
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = file_path.with_name(f"{file_path.name}.{os.getpid()}{TMP_SUFFIX}")
    written = 0
    try:
        with open(tmp_path, "wb") as f:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > expected_bytes:
                    raise ValueError(
                        f"Stream exceeded expected size ({expected_bytes} bytes)"
                    )
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
        if written != expected_bytes:
            raise ValueError(
                f"Stream ended at {written} bytes, expected {expected_bytes}"
            )
        os.replace(tmp_path, file_path)
    except (OSError, ValueError):
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return written


def get_mkpx_file_path(storage_key: UUID, storage_shard: str) -> Path:
    """Canonical path of a post's attached .mkpx layers file."""
    shard = _require_shard(storage_shard)
    return (
        get_vault_location()
        / MKPX_SUBDIR
        / Path(shard)
        / (f"{storage_key}{MKPX_EXTENSION}")
    )


def validate_mkpx_signature(head: bytes) -> bool:
    """True if ``head`` starts with either .mkpx profile signature."""
    return head.startswith(MKPX_MAGIC_PLAIN) or head.startswith(MKPX_MAGIC_COMPACT)


def save_mkpx_to_vault(
    storage_key: UUID, source, size_bytes: int, storage_shard: str
) -> Path:
    """
    Save an .mkpx layers file (streamed from ``source``, a binary file
    object positioned at 0) to the vault. No twin mirroring — the mkpx/
    namespace exists only in the v2-era tree, keyed by the stored shard
    verbatim.

    Raises:
        VaultFullError: vault below the free-space floor
        OSError / ValueError: write failure / size mismatch
    """
    ensure_vault_headroom(size_bytes)
    file_path = get_mkpx_file_path(storage_key, storage_shard)
    write_stream_atomic(file_path, source, size_bytes)
    logger.info(f"Saved mkpx for {storage_key} to {file_path}")
    return file_path


def delete_mkpx_from_vault(storage_key: UUID, storage_shard: str) -> bool:
    """
    Best-effort delete of a post's .mkpx file. Returns True if a file was
    removed; failures are logged, not raised (same posture as artwork
    deletes — orphans are acceptable, broken requests are not).
    """
    try:
        file_path = get_mkpx_file_path(storage_key, storage_shard)
    except ValueError as e:
        logger.error(f"delete_mkpx_from_vault({storage_key}): {e}")
        return False
    try:
        file_path.unlink()
        logger.info(f"Deleted mkpx for {storage_key} at {file_path}")
        return True
    except FileNotFoundError:
        return False
    except OSError as e:
        logger.warning(f"Failed to delete mkpx for {storage_key}: {e}")
        return False


def should_mirror_to_twin(
    item_id: UUID, canonical_shard: str, twin_folder: Path
) -> bool:
    """
    Asset-level dual-write rule (DECISIONS.md D10): legacy-canonical (v1)
    assets always maintain their v2 twin; v2-canonical assets mirror back
    only when the asset has a *legacy presence* (any of its files at the
    legacy path). v2-born assets get no v1 twin — the legacy tree stops
    growing at the cutover.
    """
    if len(canonical_shard) == SHARD_V1_LEN:
        return True
    if not twin_folder.is_dir():
        return False
    return any(twin_folder.glob(f"{item_id}*"))


def _mirror_to_twin(
    artwork_id: UUID, file_name: str, content: bytes, shard: str
) -> None:
    """
    Dual-location window: mirror a freshly written file to the twin path
    when the D10 rule applies. Best-effort — a failed mirror is logged
    loudly but does not fail the user's request; the reshard tooling's
    copy/verify/flip passes repair missing or stale twins (D9/D10).
    """
    try:
        twin_shard = derive_twin_shard(artwork_id, shard)
        twin_folder = get_vault_location() / Path(twin_shard)
        if not should_mirror_to_twin(artwork_id, shard, twin_folder):
            return
        write_file_atomic(twin_folder / file_name, content)
    except Exception as e:
        logger.error(
            "Dual-write mirror failed for %s (canonical shard %s): %s",
            file_name,
            shard,
            e,
        )


def save_artwork_to_vault(
    artwork_id: UUID,
    file_content: bytes,
    file_format: str,
    storage_shard: str,
) -> Path:
    """
    Save an artwork image to the vault (canonical location + twin mirror).

    Args:
        artwork_id: The UUID of the artwork (post storage_key)
        file_content: The raw bytes of the image file
        file_format: The file format (png, gif, webp, bmp)
        storage_shard: The stored shard path (required)

    Returns:
        The canonical path where the file was saved

    Raises:
        ValueError: If the file format is not allowed or shard is missing
        OSError: If there's an error writing the canonical file
    """
    if file_format not in FORMAT_TO_EXT:
        raise ValueError(
            f"File format '{file_format}' is not allowed. Allowed formats: {list(FORMAT_TO_EXT.keys())}"
        )

    shard = _require_shard(storage_shard)
    extension = FORMAT_TO_EXT[file_format]
    file_path = get_artwork_file_path(artwork_id, extension, shard)

    ensure_vault_headroom(len(file_content))
    try:
        write_file_atomic(file_path, file_content)
        logger.info(f"Saved artwork {artwork_id} to {file_path}")
    except OSError as e:
        logger.error(f"Failed to save artwork {artwork_id}: {e}")
        raise

    _mirror_to_twin(artwork_id, file_path.name, file_content, shard)
    return file_path


def save_upscaled_artwork(
    artwork_id: UUID, file_content: bytes, storage_shard: str
) -> Path:
    """
    Save the upscaled WEBP variant (canonical location + twin mirror).
    """
    shard = _require_shard(storage_shard)
    file_path = get_upscaled_file_path(artwork_id, shard)

    write_file_atomic(file_path, file_content)
    logger.info(f"Saved upscaled artwork {artwork_id} to {file_path}")

    _mirror_to_twin(artwork_id, file_path.name, file_content, shard)
    return file_path


def _delete_one(file_path: Path) -> bool:
    """Unlink one path; True if a file was removed."""
    try:
        file_path.unlink()
        return True
    except FileNotFoundError:
        return False


def delete_artwork_from_vault(
    artwork_id: UUID, extension: str, storage_shard: str
) -> bool:
    """
    Delete an artwork image from the vault — canonical location AND its twin
    (a delete during the dual-location window must not leave the other copy
    fetchable).

    Returns:
        True if at least one copy was deleted
    """
    shard = _require_shard(storage_shard)
    canonical = get_artwork_file_path(artwork_id, extension, shard)

    deleted = False
    try:
        deleted = _delete_one(canonical)
        if deleted:
            logger.info(f"Deleted artwork {artwork_id} from {canonical}")
        else:
            logger.warning(f"Artwork {artwork_id} not found at {canonical}")
    except OSError as e:
        logger.error(f"Failed to delete artwork {artwork_id}: {e}")
        raise

    try:
        twin_shard = derive_twin_shard(artwork_id, shard)
        twin = get_artwork_file_path(artwork_id, extension, twin_shard)
        if _delete_one(twin):
            logger.info(f"Deleted artwork twin {artwork_id} from {twin}")
            deleted = True
    except Exception as e:
        logger.error(f"Failed to delete artwork twin for {artwork_id}: {e}")

    return deleted


def get_artwork_url(artwork_id: UUID, extension: str, storage_shard: str) -> str:
    """
    Get the URL for accessing an artwork.

    Returns an absolute URL pointing at the Caddy vault subdomain
    (VAULT_PUBLIC_BASE_URL, required) so clients fetch images directly.

    Args:
        artwork_id: The UUID of the artwork
        extension: The file extension
        storage_shard: The stored shard path (required)

    Returns:
        URL like https://vault.makapix.club/a1/b2/<uuid>.png
    """
    shard = _require_shard(storage_shard)
    ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
    prefix = vault_public_base_url()

    return f"{prefix}/{shard}/{artwork_id}{ext}"


def validate_image_dimensions(width: int, height: int) -> tuple[bool, str | None]:
    """
    Validate image dimensions according to Makapix Club size rules.

    Rules:
    - Under 128x128: Only specific sizes allowed (8x8, 8x16, 16x8, 8x32, 32x8, 16x16, 16x32, 32x16, 32x32, 32x64, 64x32, 64x64, 64x128, 128x64)
      All 90-degree rotations of these sizes are also allowed (e.g., 8x16 and 16x8 are both valid)
    - From 128x128 to 256x256 (inclusive): Any size allowed (square or rectangular)
    - Above 256x256: Not allowed

    Args:
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        Tuple of (is_valid, error_message)
    """
    if width < 1 or height < 1:
        return False, "Image dimensions must be at least 1x1"

    # Check if either dimension exceeds 256
    if width > 256 or height > 256:
        return (
            False,
            f"Image dimensions exceed maximum of 256x256. Got {width}x{height}",
        )

    # Allowed sizes for dimensions under 128x128 (single source of truth,
    # shared with the public /config upload block). Includes both orientations.
    allowed_sizes = ALLOWED_SMALL_DIMENSIONS

    # If both dimensions are >= 128, any size is allowed (up to 256x256)
    if width >= FREE_FORM_MIN_SIZE and height >= FREE_FORM_MIN_SIZE:
        return True, None

    # Otherwise, check if the size is in the allowed list
    # This covers cases where at least one dimension is < 128
    if (width, height) not in allowed_sizes:
        # Create a sorted list for the error message (remove duplicates)
        unique_sizes = sorted(set(allowed_sizes))
        allowed_str = ", ".join([f"{w}x{h}" for w, h in unique_sizes])
        return (
            False,
            f"Image size {width}x{height} is not allowed. Under 128x128, only these sizes are allowed (rotations included): {allowed_str}",
        )

    return True, None


def validate_file_size(file_size: int) -> tuple[bool, str | None]:
    """
    Validate that the file size is within limits.

    Args:
        file_size: File size in bytes

    Returns:
        Tuple of (is_valid, error_message)
    """
    if file_size > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        return False, f"File size ({actual_mb:.2f} MB) exceeds maximum of {max_mb} MB"

    return True, None


def get_upscaled_file_path(artwork_id: UUID, storage_shard: str) -> Path:
    """
    Get the path for an upscaled artwork file.

    The upscaled file is stored in the same vault folder as the original,
    with "_upscaled.webp" suffix.

    Args:
        artwork_id: The UUID of the artwork (storage_key)
        storage_shard: The stored shard path (required)

    Returns:
        Path to the upscaled WEBP file: {folder}/{artwork_id}_upscaled.webp
    """
    folder_path = get_artwork_folder_path(artwork_id, storage_shard)
    return folder_path / f"{artwork_id}_upscaled.webp"


def delete_all_artwork_formats(
    artwork_id: UUID, formats: list[str], storage_shard: str
) -> dict[str, bool]:
    """
    Delete all format variants of an artwork plus the upscaled version,
    from the canonical location and its twin.

    Args:
        artwork_id: The UUID of the artwork (storage_key)
        formats: List of file formats to delete (e.g., ['png', 'gif', 'webp', 'bmp'])
        storage_shard: The stored shard path (required)

    Returns:
        Dictionary mapping format/type to deletion success status
        Example: {'png': True, 'gif': True, 'upscaled': True}
    """
    shard = _require_shard(storage_shard)
    results = {}

    # Delete each format variant (canonical + twin handled by the primitive)
    for file_format in formats:
        if file_format in FORMAT_TO_EXT:
            extension = FORMAT_TO_EXT[file_format]
            try:
                deleted = delete_artwork_from_vault(artwork_id, extension, shard)
                results[file_format] = deleted
            except Exception as e:
                logger.warning(f"Failed to delete {file_format} for {artwork_id}: {e}")
                results[file_format] = False

    # Delete upscaled version from both locations
    deleted_upscaled = False
    try:
        upscaled_path = get_upscaled_file_path(artwork_id, shard)
        if _delete_one(upscaled_path):
            logger.info(f"Deleted upscaled file for {artwork_id}")
            deleted_upscaled = True
        twin_shard = derive_twin_shard(artwork_id, shard)
        twin_upscaled = get_upscaled_file_path(artwork_id, twin_shard)
        if _delete_one(twin_upscaled):
            logger.info(f"Deleted upscaled twin for {artwork_id}")
            deleted_upscaled = True
    except Exception as e:
        logger.warning(f"Failed to delete upscaled file for {artwork_id}: {e}")
    results["upscaled"] = deleted_upscaled

    return results
