"""Environment probe — know what is installed *before* writing code that needs it.

A phone sandbox is not a laptop: `reportlab` is missing, `pip install` can take
twenty minutes or fail outright, and `pandoc` was never there. Assuming is how
agents waste a turn and then apologise. So the agent gets a probe instead:

* a compact summary is injected into the system prompt every turn
* the `check_environment` tool answers precise questions ("is openpyxl here?")
* results are cached briefly, because the answer barely ever changes

Nothing here shells out to `pip` or installs anything — it only reports.
"""

from __future__ import annotations

import importlib.util
import platform
import shutil
import sys
import time
from typing import Iterable

# Python packages worth knowing about, grouped by what they would be used for.
PACKAGE_GROUPS: dict[str, tuple[str, ...]] = {
    "pdf": ("reportlab", "fpdf", "weasyprint", "pypdf", "PyPDF2", "fitz", "pdfplumber"),
    "docs": ("docx", "openpyxl", "pptx", "xlsxwriter", "markdown", "pygments"),
    "data": ("pandas", "numpy", "matplotlib", "PIL", "csv", "sqlite3"),
    "web": ("requests", "httpx", "bs4", "lxml", "flask"),
    "agent": ("mcp", "openai", "anthropic", "tiktoken"),
}

# Command-line tools the agent reaches for.
CLI_TOOLS = (
    "python3", "pip", "node", "npm", "git", "curl", "wget", "jq", "sqlite3",
    "pandoc", "wkhtmltopdf", "libreoffice", "ffmpeg", "convert", "magick",
    "tesseract", "pdftoppm", "pdfinfo", "qpdf", "gs", "zip", "unzip", "tar",
    "grep", "sed", "awk", "find", "file",
)

CACHE_TTL = 60.0
_cache: dict[str, object] = {"at": 0.0, "data": None}


def _module_available(name: str) -> tuple[bool, str]:
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError, ModuleNotFoundError):
        return False, ""
    if spec is None:
        return False, ""
    origin = getattr(spec, "origin", "") or ""
    return True, origin


def _version_of(module_name: str) -> str:
    """Distribution version without importing the module (imports cost seconds)."""
    try:
        from importlib import metadata

        for dist in (module_name, module_name.replace("_", "-")):
            try:
                return metadata.version(dist)[:12]
            except metadata.PackageNotFoundError:
                continue
    except Exception:
        pass
    return ""


def probe(refresh: bool = False) -> dict:
    """Return a cached description of this machine's actual capabilities."""
    now = time.time()
    if not refresh and _cache["data"] and now - float(_cache["at"]) < CACHE_TTL:
        return _cache["data"]  # type: ignore[return-value]

    cli = {tool: (shutil.which(tool) or "") for tool in CLI_TOOLS}
    packages: dict[str, dict] = {}
    for group, names in PACKAGE_GROUPS.items():
        for name in names:
            available, origin = _module_available(name)
            packages[name] = {
                "group": group,
                "available": available,
                "version": _version_of(name) if available else "",
                "path": origin if available else "",
            }

    data = {
        "at": now,
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cli": cli,
        "packages": packages,
        "third_party_packages": sorted(n for n, p in packages.items() if p["available"]),
        "missing_packages": sorted(n for n, p in packages.items() if not p["available"]),
        "available_cli": sorted(t for t, p in cli.items() if p),
    }
    _cache.update({"at": now, "data": data})
    return data


def _known_packages() -> set[str]:
    return {name.replace("-", "_") for names in PACKAGE_GROUPS.values() for name in names}


def check(names: Iterable[str]) -> dict[str, dict]:
    """Check specific names — modules first, then binaries."""
    out: dict[str, dict] = {}
    for raw in names:
        name = str(raw).strip()
        if not name:
            continue
        key = name.replace("-", "_")
        available, origin = _module_available(key)
        known_pkg = key in _known_packages()
        if available or known_pkg:
            out[name] = {
                "kind": "module",
                "available": available,
                "version": _version_of(key) if available else "",
                "path": origin if available else "",
            }
        elif name in CLI_TOOLS or shutil.which(name):
            out[name] = {
                "kind": "binary",
                "available": bool(shutil.which(name)),
                "version": "",
                "path": shutil.which(name) or "",
            }
        else:
            out[name] = {"kind": "unknown", "available": False, "version": "", "path": ""}
    return out


def prompt_block() -> str:
    """Compact, stable summary for the system prompt."""
    data = probe()
    have = data["available_cli"]
    # Keep the prompt small: name only the tools worth knowing about.
    useful = [t for t in ("git", "node", "npm", "curl", "jq", "sqlite3", "pdftoppm",
                          "pdfinfo", "qpdf", "ffmpeg", "pandoc", "libreoffice",
                          "convert", "tesseract") if t in have]
    doc_libs = [p for p in ("reportlab", "weasyprint", "fpdf", "matplotlib", "pandas",
                            "openpyxl", "docx", "pptx", "PIL") if p in data["third_party_packages"]]
    missing_doc = [p for p in ("reportlab", "weasyprint", "matplotlib", "pandas", "pandoc")
                   if p in data["missing_packages"]]

    lines = [
        "## ENVIRONMENT (probed, not assumed)",
        f"- Python {data['python']} on {data['platform']}",
        f"- CLI available: {', '.join(useful) if useful else 'basic shell only'}",
        f"- Document/data libraries present: {', '.join(doc_libs) if doc_libs else 'none — use the stdlib toolkit and skills'}",
    ]
    if missing_doc:
        lines.append(f"- NOT installed: {', '.join(missing_doc)}")
    lines.append(
        "- Rule: check before you import. Call `check_environment` for anything not listed "
        "above. Never `pip install` unless the user asks — it is slow or broken on-device. "
        "If a tool is missing, say which one and use the stdlib path instead."
    )
    return "\n".join(lines)
