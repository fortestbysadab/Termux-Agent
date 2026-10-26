"""Per-session isolated terminal sandbox runner for Termux and Linux environments."""

import os
import resource
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any
from config import WORKSPACES_DIR

EMPTY_DUMMY_DIR = Path.home() / ".agent_empty_dummy"
EMPTY_DUMMY_DIR.mkdir(parents=True, exist_ok=True)

class SessionSandbox:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.workspace_dir = (WORKSPACES_DIR / session_id).resolve()
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.has_proot = shutil.which("proot") is not None

    def run_command(self, command: str, timeout_seconds: float = 60.0) -> dict[str, Any]:
        """Execute a shell command inside the isolated session workspace."""
        start_time = time.monotonic()
        
        # Build safe environment
        safe_env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "PREFIX": os.environ.get("PREFIX", "/usr"),
            "HOME": str(self.workspace_dir),
            "PWD": str(self.workspace_dir),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TERM": "xterm-256color",
            "TMPDIR": str(self.workspace_dir / ".tmp"),
        }
        (self.workspace_dir / ".tmp").mkdir(exist_ok=True)

        # Ensure no parent API keys or secrets leak into command
        for k in list(safe_env.keys()):
            if any(term in k.upper() for term in ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH")):
                safe_env.pop(k, None)

        def preexec():
            # Create a new process group so we can kill any child processes if timeout
            os.setsid()
            try:
                # 50s CPU time limit, 2GB address space limit
                resource.setrlimit(resource.RLIMIT_CPU, (int(timeout_seconds), int(timeout_seconds) + 5))
                resource.setrlimit(resource.RLIMIT_AS, (2 * 1024 * 1024 * 1024, 2 * 1024 * 1024 * 1024))
            except Exception:
                pass

        use_proot = self.has_proot
        if use_proot:
            cmd = [
                "proot",
                "-b", f"{EMPTY_DUMMY_DIR}:{Path.home()}",
                "-b", f"{EMPTY_DUMMY_DIR}:/sdcard",
                "-b", f"{self.workspace_dir}:/workspace",
                "-w", "/workspace",
                "bash", "-c", command,
            ]
        else:
            cmd = ["bash", "-c", command]

        proc = None
        timed_out = False
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.workspace_dir),
                env=safe_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=preexec,
            )
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            if proc:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    pass
                try:
                    proc.kill()
                    stdout, stderr = proc.communicate(timeout=1.0)
                except Exception:
                    stdout, stderr = "", "Process timed out and was killed."
            exit_code = -1
        except Exception as e:
            stdout = ""
            stderr = f"Execution error: {str(e)}"
            exit_code = -1

        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Truncate large outputs
        max_chars = 16000
        if len(stdout) > max_chars:
            stdout = stdout[:max_chars] + f"\n... [Output truncated. {len(stdout) - max_chars} characters omitted]"
        if len(stderr) > max_chars:
            stderr = stderr[:max_chars] + f"\n... [Stderr truncated. {len(stderr) - max_chars} characters omitted]"

        return {
            "ok": exit_code == 0,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "timed_out": timed_out,
            "workspace": str(self.workspace_dir),
        }
