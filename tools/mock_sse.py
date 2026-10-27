#!/usr/bin/env python3
"""Design-verification harness — NOT part of the app.

Serves the built console and replays a scripted agent turn over SSE so the
live UI states (orb phases, border-beam intensity, avatar hand-off, tool cards,
error card) can be screenshotted without an LLM key. Every other /api/* request
is proxied to the real server on :8080.

    python3 tools/mock_sse.py 8099
"""

import json
import sys
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "web" / "static"
UPSTREAM = "http://127.0.0.1:8080"


def proxy(method, path, body):
    req = urllib.request.Request(
        UPSTREAM + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read()


SCRIPT = [
    (0.2, "status", {"message": "Planning turn 1..."}),
    (0.5, "command_start", {"command": "python3 -c \"build_xlsx+svg\"", "tool": "terminal"}),
    (1.6, "command_done", {
        "tool": "terminal",
        "command": "python3 -c \"build_xlsx+svg\"",
        "stdout": "wrote study_plan.xlsx (4.2 KB)\nwrote focus_chart.svg (1.8 KB)\n",
        "stderr": "", "exit_code": 0, "duration_ms": 1432, "ok": True,
    }),
    (0.6, "status", {"message": "Planning turn 2..."}),
    (0.4, "connector_start", {"tool": "github_list_repos", "arguments": {}}),
    (1.8, "connector_done", {
        "tool": "github_list_repos",
        "arguments": {},
        "result": [{"name": "Termux-Agent", "stars": 42}],
        "ok": True,
    }),
    (0.5, "command_start", {"command": "pip install matplotlib", "tool": "terminal"}),
    (1.1, "command_done", {
        "tool": "terminal",
        "command": "pip install matplotlib",
        "stdout": "",
        "stderr": "Termux Environment Notice: Compiling heavy C/C++ packages from source via pip "
                  "times out on Android ARM64 devices.\n-> Generate SVG instead.",
        "exit_code": 1, "duration_ms": 10, "ok": False,
    }),
    (1.0, "status", {"message": "Planning turn 3..."}),
    (1.4, "done", {
        "message": {
            "role": "assistant",
            "created_at": time.time(),
            "content": "I built both deliverables in the session sandbox.\n\n"
                       "| File | What it is |\n|---|---|\n| `study_plan.xlsx` | 7-day schedule |\n"
                       "| `focus_chart.svg` | vector chart |\n\n"
                       "I skipped `matplotlib` — it can't compile here, so the chart is pure SVG.",
        },
        "tool_runs": [],
        "files_generated": [
            {"filename": "study_plan.xlsx", "rel_path": "study_plan.xlsx", "size_bytes": 4312},
            {"filename": "focus_chart.svg", "rel_path": "focus_chart.svg", "size_bytes": 1840},
        ],
        "error": None,
    }),
]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _static(self, path):
        rel = path.lstrip("/") or "index.html"
        target = (STATIC / rel).resolve()
        if not target.is_file():
            return False
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".map": "application/json",
        }.get(target.suffix, "application/octet-stream")
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)
        return True

    def do_GET(self):
        if self._static(self.path.split("?")[0]):
            return
        status, body = proxy("GET", self.path, None)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        body = json.loads(raw or b"{}")

        if self.path != "/api/chat":
            try:
                status, data = proxy("POST", self.path, body)
            except Exception as exc:  # noqa: BLE001
                status, data = 500, json.dumps({"error": str(exc)}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        for delay, event, payload in SCRIPT:
            time.sleep(delay)
            frame = f"event: {event}\ndata: {json.dumps(payload)}\n\n"
            try:
                self.wfile.write(frame.encode())
                self.wfile.flush()
            except Exception:  # noqa: BLE001
                break
        self.close_connection = True


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
    print(f"mock harness on http://127.0.0.1:{port} (proxying {UPSTREAM})")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
