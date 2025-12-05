"""Bundle and manifest validation utilities."""

import json
import os
import zipfile
from pathlib import Path
from typing import Tuple, List

MAX_BUNDLE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB per artwork
ALLOWED_CANVASES = ["16x16", "32x32", "64x64", "128x128", "256x256"]


def is_safe_path(base_path: Path, target_path: str) -> bool:
    """
    Check if a path is safe (no path traversal).
    
    Args:
        base_path: The base directory path
        target_path: The target path to validate
        
    Returns:
        True if path is safe, False otherwise
    """
    try:
        # Resolve both paths to absolute paths
        base = base_path.resolve()
        target = (base_path / target_path).resolve()
        
        # Check if target is within base directory
        return target.is_relative_to(base)
    except (ValueError, OSError):
        return False


def validate_zip_structure(zip_path: Path) -> Tuple[bool, List[str]]:
    """Validate ZIP structure and safety."""
    errors = []
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Check for path traversal and unsafe paths
            for name in zf.namelist():
                # Reject absolute paths
                if name.startswith('/') or name.startswith('\\'):
                    errors.append(f"Absolute path not allowed: {name}")
                    continue
                
                # Reject parent directory references
                if '..' in name.split(os.sep):
                    errors.append(f"Parent directory reference not allowed: {name}")
                    continue
                
                # Reject paths with drive letters (Windows)
                if ':' in name:
                    errors.append(f"Drive letter not allowed: {name}")
                    continue
                
                # Additional check using Path
                if not is_safe_path(Path('.'), name):
                    errors.append(f"Unsafe path: {name}")
                    continue
                
                # Check for symbolic links (security risk)
                info = zf.getinfo(name)
                # Check if it's a symbolic link using Unix file type
                # 0o120000 = S_IFLNK (symbolic link file type on Unix systems)
                UNIX_SYMLINK_TYPE = 0o120000
                if info.external_attr >> 16 == UNIX_SYMLINK_TYPE:
                    errors.append(f"Symbolic links not allowed: {name}")
            
            # Check total size
            total_size = sum(info.file_size for info in zf.infolist())
            if total_size > MAX_BUNDLE_SIZE:
                errors.append(f"Bundle too large: {total_size} bytes (max: {MAX_BUNDLE_SIZE})")
            
            # Require manifest.json
            if 'manifest.json' not in zf.namelist():
                errors.append("Missing manifest.json")
    except zipfile.BadZipFile:
        errors.append("Invalid ZIP file")
    except Exception as e:
        errors.append(f"Error reading ZIP file: {str(e)}")
    
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
        if not isinstance(manifest["artworks"], list):
            errors.append("Artworks must be a list")
        else:
            for idx, art in enumerate(manifest["artworks"]):
                if not isinstance(art, dict):
                    errors.append(f"Artwork {idx} must be an object")
                    continue
                
                # Title validation
                title = art.get("title")
                if not title:
                    errors.append(f"Missing title in artwork {idx}")
                elif not isinstance(title, str):
                    errors.append(f"Invalid title type in artwork {idx}")
                elif len(title) > 200:
                    errors.append(f"Title too long in artwork {idx} (max 200 chars)")
                
                # Canvas validation
                canvas = art.get("canvas")
                if canvas not in ALLOWED_CANVASES:
                    errors.append(f"Invalid canvas in artwork {idx}: {canvas}. Allowed: {ALLOWED_CANVASES}")
                
                # File size validation
                file_kb = art.get("file_kb", 0)
                if not isinstance(file_kb, (int, float)):
                    errors.append(f"Invalid file_kb type in artwork {idx}")
                else:
                    max_file_kb = MAX_FILE_SIZE / 1024
                    if file_kb > max_file_kb:
                        errors.append(f"File too large in artwork {idx}: {file_kb}KB exceeds limit of {max_file_kb}KB")
    
    return len(errors) == 0, errors
