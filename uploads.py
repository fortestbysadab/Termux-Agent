"""Upload handling — multipart/form-data parsing and safe workspace storage.

Python 3.13 removed the `cgi` module, so this parses multipart bodies with
`email.parser`, which is stdlib, streaming-friendly and handles binary payloads
without corrupting them.

Files are always written into `<session workspace>/uploads/`, which means they
are readable by the agent's shell tool, included in the workspace ZIP, and
cleaned up when the session is deleted — no separate storage to keep in sync.
"""

from __future__ import annotations

import re
import unicodedata
from email.parser import BytesParser
from email.policy import HTTP
from pathlib import Path
from typing import Any

from config import MAX_UPLOAD_BYTES, UPLOADS_SUBDIR

ALLOWED_EXTENSIONS = {
    # documents & data
    ".pdf", ".docx", ".xlsx", ".xlsm", ".pptx", ".odt", ".ods", ".odp", ".rtf",
    ".csv", ".tsv", ".json", ".jsonl", ".xml", ".yaml", ".yml", ".txt", ".md",
    ".html", ".htm", ".log",
    # images & media
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp", ".heic",
    ".mp3", ".wav", ".m4a", ".ogg", ".mp4", ".webm", ".mov",
    # archives & code the agent may need to inspect
    ".zip", ".tar", ".gz", ".tgz", ".7z",
    ".py", ".js", ".ts", ".sh", ".c", ".h", ".cpp", ".java", ".rb", ".go", ".rs",
    ".sql", ".ini", ".cfg", ".toml", ".env.example",
}

_UNSAFE = re.compile(r"[^A-Za-z0-9._ ()\[\]-]+")


class UploadError(ValueError):
    """User-facing upload problem (bad name, too large, wrong type)."""


def sanitize_filename(raw: str) -> str:
    """Basename only, no traversal, no control characters, no leading dots."""
    name = Path(str(raw or "")).name.strip()
    name = unicodedata.normalize("NFKC", name)
    name = _UNSAFE.sub("_", name).replace("..", ".")
    name = name.strip(" ._")
    if not name:
        raise UploadError("The file needs a name.")
    stem = Path(name).stem[:80] or "file"
    suffix = Path(name).suffix[:16]
    return f"{stem}{suffix}"


def check_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if not suffix:
        raise UploadError(f"'{filename}' has no extension, so its type is unknown.")
    if suffix not in ALLOWED_EXTENSIONS:
        raise UploadError(
            f"'{suffix}' files are not supported. Allowed: data, documents, images, "
            "media, archives and source code."
        )
    return suffix


def unique_path(directory: Path, filename: str) -> Path:
    """Never overwrite: `report.pdf` → `report (2).pdf`."""
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem, suffix = Path(filename).stem, Path(filename).suffix
    for n in range(2, 1000):
        candidate = directory / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
    raise UploadError(f"Too many files named like '{filename}'.")


def parse_multipart(content_type: str, body: bytes) -> list[dict[str, Any]]:
    """Return [{filename, data}] from a multipart/form-data body."""
    if "multipart/form-data" not in content_type.lower():
        raise UploadError("Expected a multipart/form-data upload.")
    if len(body) > MAX_UPLOAD_BYTES * 4:  # rough guard before parsing
        raise UploadError("Upload too large.")

    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
    message = BytesParser(policy=HTTP).parsebytes(header + body)

    if not message.is_multipart():
        raise UploadError("Malformed multipart body.")

    files: list[dict[str, Any]] = []
    for part in message.iter_parts():
        if part.get_content_disposition() != "attachment" and part.get_param(
            "name", header="content-disposition"
        ) not in ("file", "files", "upload", None):
            continue
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True) or b""
        if len(payload) > MAX_UPLOAD_BYTES:
            raise UploadError(
                f"'{filename}' is larger than the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit."
            )
        files.append({"filename": filename, "data": payload})

    if not files:
        raise UploadError("No file was found in the request.")
    return files


def store_uploads(workspace_dir: Path, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Write parsed files into `<workspace>/uploads/` and describe them."""
    upload_dir = Path(workspace_dir) / UPLOADS_SUBDIR
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored: list[dict[str, Any]] = []
    for item in files:
        clean = sanitize_filename(item["filename"])
        check_extension(clean)
        target = unique_path(upload_dir, clean)
        target.write_bytes(item["data"])
        stored.append(
            {
                "filename": target.name,
                "original_name": item["filename"],
                "rel_path": f"{UPLOADS_SUBDIR}/{target.name}",
                "size": target.stat().st_size,
            }
        )
    return stored
