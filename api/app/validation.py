"""Bundle and manifest validation utilities."""

import json
import zipfile
from pathlib import Path
from typing import Tuple, List

MAX_BUNDLE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_FILE_SIZE = 350 * 1024  # 350 KB per artwork
ALLOWED_CANVASES = ["16x16", "32x32", "64x64", "128x128", "256x256"]


def validate_zip_structure(zip_path: Path) -> Tuple[bool, List[str]]:
    """Validate ZIP structure and safety."""
    errors = []
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Check for path traversal
            for name in zf.namelist():
                if name.startswith('/') or '..' in name:
                    errors.append(f"Unsafe path: {name}")
            
            # Check total size
            total_size = sum(info.file_size for info in zf.infolist())
            if total_size > MAX_BUNDLE_SIZE:
                errors.append(f"Bundle too large: {total_size} bytes")
            
            # Require manifest.json
            if 'manifest.json' not in zf.namelist():
                errors.append("Missing manifest.json")
    except zipfile.BadZipFile:
        errors.append("Invalid ZIP file")
    
    return len(errors) == 0, errors


def validate_manifest(manifest: dict) -> Tuple[bool, List[str]]:
    """Validate manifest schema and content."""
    errors = []
    
    # Required fields
    required = ["artworks", "version"]
    for field in required:
        if field not in manifest:
            errors.append(f"Missing required field: {field}")
    
    # Validate artworks
    if "artworks" in manifest:
        for idx, art in enumerate(manifest["artworks"]):
            # Title validation
            if not art.get("title") or len(art["title"]) > 200:
                errors.append(f"Invalid title in artwork {idx}")
            
            # Canvas validation
            if art.get("canvas") not in ALLOWED_CANVASES:
                errors.append(f"Invalid canvas in artwork {idx}: {art.get('canvas')}")
            
            # File size validation
            if art.get("file_kb", 0) > MAX_FILE_SIZE / 1024:
                errors.append(f"File too large in artwork {idx}")
    
    return len(errors) == 0, errors
