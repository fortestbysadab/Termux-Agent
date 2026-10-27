"""Vision — hand images to the model directly instead of making it shell out.

The planner talks to a multimodal model (Gemini 2.5, GPT-4o, Claude…), so an
attached photo or screenshot can go *into the turn* as image content. Writing a
Python script to describe a PNG is wasted effort — and on a phone it is wasted
battery too. Python stays the fallback for models that cannot see, and for
formats no model can read natively yet (PDF page layout, XLSX, ZIP…).

``AGENT_VISION=auto`` (default) decides from the model name; ``on``/``off``
force it.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any, Iterable

from config import INLINE_IMAGE_EXTS, INLINE_IMAGE_MAX_BYTES, VISION_MODE, VISION_MODEL_HINTS

MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def model_has_vision(model: str | None = None, mode: str | None = None) -> bool:
    """True when this model can be handed image content parts."""
    mode = (mode or VISION_MODE or "auto").lower()
    if mode in ("0", "off", "false", "no"):
        return False
    if mode in ("1", "on", "true", "yes"):
        return True
    name = (model or "").lower()
    return any(hint in name for hint in VISION_MODEL_HINTS)


def is_image(filename: str) -> bool:
    return Path(str(filename)).suffix.lower() in INLINE_IMAGE_EXTS


def image_part(path: Path) -> dict[str, Any] | None:
    """One OpenAI-compatible `image_url` part, or None if it cannot be inlined."""
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return None
    if not raw or len(raw) > INLINE_IMAGE_MAX_BYTES:
        return None
    mime = MIME_BY_EXT.get(Path(path).suffix.lower()) or mimetypes.guess_type(str(path))[0] or "image/png"
    encoded = base64.b64encode(raw).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}


def build_content(
    text: str,
    attachments: Iterable[dict[str, Any]] | None,
    workspace_dir: Path | str,
    model: str | None = None,
) -> tuple[Any, list[str]]:
    """Return (message content, notes) for a user turn.

    ``content`` is a plain string when nothing can be inlined (the normal case),
    or a list of OpenAI-style parts when images are attached.
    """
    attachments = [a for a in (attachments or []) if a.get("filename")]
    if not attachments or not model_has_vision(model):
        return text, []

    parts: list[dict[str, Any]] = []
    notes: list[str] = []
    for item in attachments:
        name = item.get("filename")
        if not is_image(name):
            continue
        candidate = Path(workspace_dir) / (item.get("rel_path") or f"uploads/{name}")
        part = image_part(candidate)
        if part:
            parts.append(part)
            notes.append(name)

    if not parts:
        return text, []

    return [{"type": "text", "text": text}, *parts], notes


def capability_note(model: str | None = None) -> str:
    """One line for the system prompt describing what the model can see."""
    if model_has_vision(model):
        return (
            "VISION: you can see attached images (png/jpg/webp/gif) directly — they arrive in the "
            "conversation as image content. Look at them before reaching for a script. Use Python "
            "only for what you cannot see: PDF page layout, spreadsheets, archives, video, audio, "
            "or when pixels need measuring (dimensions, OCR at scale, colour maths)."
        )
    return (
        "VISION: this model cannot see images. For any image or PDF the user attaches, inspect it "
        "with shell tooling (python3, file, exiftool-style parsing) and say what you did."
    )
