"""Configuration settings for Termux Agent."""

import os
from pathlib import Path

def load_dotenv(path: str = ".env") -> None:
    """Lightweight .env loader without third-party dependencies."""
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip("'\"")
        if k and k not in os.environ:
            os.environ[k] = v

load_dotenv()

HOST = os.environ.get("AGENT_HOST", "0.0.0.0")
PORT = int(os.environ.get("AGENT_PORT", "8080"))

# LLM Configuration
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-2.5-flash")

# Storage Configuration
DATA_DIR = Path(os.environ.get("AGENT_DATA_DIR", Path.home() / ".termux_agent_data")).expanduser()
WORKSPACES_DIR = DATA_DIR / "workspaces"
DB_PATH = DATA_DIR / "agent.db"

# Uploads live inside each session workspace so the agent can read them
# with ordinary shell commands, and so they are covered by the ZIP download.
UPLOADS_SUBDIR = "uploads"
MAX_UPLOAD_BYTES = int(os.environ.get("AGENT_MAX_UPLOAD_MB", "25")) * 1024 * 1024

# Skills: markdown procedures shipped with the repo (read-only at runtime).
SKILLS_DIR = Path(os.environ.get("AGENT_SKILLS_DIR", Path(__file__).resolve().parent / "skills"))
SKILLS_ENABLED_BY_DEFAULT = os.environ.get("AGENT_SKILLS_DEFAULT", "1") not in ("0", "false", "no")
# Skill router: auto-load matching skills (and their dependencies) before the model speaks.
SKILL_ROUTER = os.environ.get("AGENT_SKILL_ROUTER", "1") not in ("0", "false", "no")

# Vision: if the model can see, attached images go straight into the turn
# instead of being described by a Python script. auto|on|off
VISION_MODE = os.environ.get("AGENT_VISION", "auto").lower()
INLINE_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
INLINE_IMAGE_MAX_BYTES = int(os.environ.get("AGENT_VISION_MAX_MB", "6")) * 1024 * 1024
VISION_MODEL_HINTS = (
    "gemini", "gpt-4o", "gpt-4.1", "gpt-5", "o3", "o4", "claude", "grok",
    "pixtral", "llava", "qwen-vl", "qwen2-vl", "internvl", "minicpm",
)

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
