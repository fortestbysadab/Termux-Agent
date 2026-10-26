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

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
