#!/usr/bin/env python3
"""AMP Inspector - Artwork Metadata Platform CLI tool.

Standalone script for inspecting and validating artwork files.
Can be used from command line or called by the backend via subprocess.

Usage:
    # Human-friendly mode (prints progress messages)
    python -m app.amp.amp_inspector /path/to/image.png

    # Backend mode (silent, JSON only)
    python -m app.amp.amp_inspector --backend /path/to/image.png
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

from .constants import MAX_FILE_SIZE_BYTES
from .header_inspection import inspect_header
from .metadata_extraction import extract_metadata


def main() -> int:
    """Main entry point for AMP inspector."""
    parser = argparse.ArgumentParser(
        description="Artwork Metadata Platform Inspector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "file_path",
        type=Path,
        help="Path to the artwork file to inspect",
    )

    parser.add_argument(
        "--backend",
        action="store_true",
        help="Backend mode: suppress console output, JSON only",
    )

    parser.add_argument(
        "--max-file-size",
        type=int,
        default=MAX_FILE_SIZE_BYTES,
        help=f"Maximum file size in bytes (default: {MAX_FILE_SIZE_BYTES})",
    )

    parser.add_argument(
        "--skip-pixel-scan",
        action="store_true",
        help="Skip transparency/color pixel scanning (for testing)",
    )

    args = parser.parse_args()

    # Validate file exists
    if not args.file_path.exists():
        return _output_error(
            "FILE_NOT_FOUND",
            f"File not found: {args.file_path}",
            args.backend,
            exit_code=1,
        )

    if not args.file_path.is_file():
        return _output_error(
            "NOT_A_FILE",
            f"Path is not a file: {args.file_path}",
            args.backend,
            exit_code=1,
        )

    # Phase A: Header inspection (fail-fast)
    if not args.backend:
        print(f"Inspecting file: {args.file_path}", file=sys.stderr)
        print("Phase A: Header inspection...", file=sys.stderr)

    header_result = inspect_header(args.file_path)

    if not header_result.success:
        return _output_error(
            header_result.error_code,
            header_result.error_message,
            args.backend,
            exit_code=1,
        )

    if not args.backend:
        print(
            f"  ✓ Extension: {args.file_path.suffix}",
            file=sys.stderr,
        )
        print(
            f"  ✓ Dimensions: {header_result.width}x{header_result.height}",
            file=sys.stderr,
        )
        print(
            f"  ✓ File size: {args.file_path.stat().st_size:,} bytes",
            file=sys.stderr,
        )

    # Phase B: Pillow loading and metadata extraction
    if not args.backend:
        print("Phase B: Loading image with Pillow...", file=sys.stderr)

    try:
        # Use a context manager so the underlying file handle is closed
        # as soon as Pillow is done reading it (required by AMP spec).
        with Image.open(args.file_path) as img:
            if not args.backend:
                print("Phase B: Extracting metadata...", file=sys.stderr)

            try:
                metadata = extract_metadata(args.file_path, img)
            except Exception as e:
                return _output_error(
                    "METADATA_EXTRACTION_FAILED",
                    f"Failed to extract metadata: {e}",
                    args.backend,
                    exit_code=2,
                )
    except Exception as e:
        return _output_error(
            "PILLOW_LOAD_FAILED",
            f"Pillow failed to load image: {e}",
            args.backend,
            exit_code=1,
        )

    # Phase B (continued): After Pillow is finished and its file handle is closed,
    # compute SHA256 of the entire file (required by AMP spec).
    try:
        digest = hashlib.sha256()
        with args.file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        sha256_hex = digest.hexdigest()
    except Exception as e:
        return _output_error(
            "HASH_COMPUTE_FAILED",
            f"Failed to compute SHA256: {e}",
            args.backend,
            exit_code=2,
        )

    # Output success result as JSON
    result = {
        "success": True,
        "metadata": {
            "width": metadata.width,
            "height": metadata.height,
            "base": metadata.base,
            "size": metadata.size,
            "file_bytes": metadata.file_bytes,
            "file_format": metadata.file_format,
            "frame_count": metadata.frame_count,
            "shortest_duration_ms": metadata.shortest_duration_ms,
            "longest_duration_ms": metadata.longest_duration_ms,
            "unique_colors": metadata.unique_colors,
            "transparency_meta": metadata.transparency_meta,
            "alpha_meta": metadata.alpha_meta,
            "transparency_actual": metadata.transparency_actual,
            "alpha_actual": metadata.alpha_actual,
            "sha256": sha256_hex,
        },
    }

    if not args.backend:
        print("\n✓ Inspection complete!", file=sys.stderr)
        print("\nMetadata:", file=sys.stderr)
        print(json.dumps(result, indent=2), file=sys.stderr)
        print("\nJSON output:", file=sys.stderr)

    # Always output JSON to stdout (for backend parsing)
    print(json.dumps(result))
    return 0


def _output_error(
    error_code: str,
    error_message: str,
    backend_mode: bool,
    exit_code: int = 1,
) -> int:
    """
    Output error in JSON format and return exit code.

    Args:
        error_code: Machine-readable error code
        error_message: Human-readable error message
        backend_mode: If True, suppress stderr output
        exit_code: Exit code to return

    Returns:
        The exit code
    """
    error_result = {
        "success": False,
        "error": {
            "code": error_code,
            "message": error_message,
        },
    }

    if not backend_mode:
        print(f"\n✗ Error: {error_message}", file=sys.stderr)
        print("\nJSON output:", file=sys.stderr)

    print(json.dumps(error_result))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
