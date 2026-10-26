"""Tracks file modifications and creations in session workspaces."""

import hashlib
import os
from pathlib import Path
from typing import Any

def _file_hash(path: Path) -> str:
    """Computes quick MD5 hash of file content."""
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""

def snapshot_workspace(workspace_dir: Path) -> dict[str, dict[str, Any]]:
    """Recursively scans workspace and returns state map: {rel_path: {size, mtime, hash}}."""
    manifest = {}
    if not workspace_dir.is_dir():
        return manifest

    for root, _, files in os.walk(workspace_dir):
        for f in files:
            full_path = Path(root) / f
            try:
                stat = full_path.stat()
                rel = str(full_path.relative_to(workspace_dir))
                manifest[rel] = {
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                    "hash": _file_hash(full_path),
                }
            except (OSError, FileNotFoundError):
                continue
    return manifest

def diff_workspace(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]]
) -> dict[str, list[str]]:
    """Calculates created and modified files between two snapshots."""
    created = []
    modified = []

    for rel, meta in after.items():
        if rel not in before:
            created.append(rel)
        elif before[rel]["hash"] != meta["hash"] or before[rel]["size"] != meta["size"]:
            modified.append(rel)

    return {
        "created": created,
        "modified": modified,
        "all_changed": created + modified,
    }
