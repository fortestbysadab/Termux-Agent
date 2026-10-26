"""HTTP Web Server for Termux Agent."""

import json
import mimetypes
import os
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from config import HOST, PORT, WORKSPACES_DIR
from db import (
    init_db,
    list_sessions,
    create_session,
    get_session,
    delete_session,
    clear_all_sessions,
    get_messages,
    list_artifacts,
    upsert_connector,
    toggle_connector,
    delete_connector,
)
from connectors.manager import ConnectorManager
from agent.loop import AgentRunner
from sandbox.runner import SessionSandbox
from sandbox.tracker import snapshot_workspace

STATIC_DIR = Path(__file__).parent / "static"

def parse_spreadsheet_data(target: Path) -> dict:
    ext = target.suffix.lower()
    if ext == ".csv":
        import csv
        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                rows = [row for row in reader]
            return {
                "type": "spreadsheet",
                "filename": target.name,
                "sheets": [{"name": target.name, "rows": rows[:200]}]
            }
        except Exception as e:
            return {"type": "error", "error": f"Failed to parse CSV: {str(e)}"}
    elif ext in (".xlsx", ".xlsm"):
        # First try openpyxl if installed
        try:
            import openpyxl
            wb = openpyxl.load_workbook(target, data_only=True)
            sheets = []
            for sheet_name in wb.sheetnames[:5]:
                ws = wb[sheet_name]
                rows = []
                for row in ws.iter_rows(values_only=True):
                    if any(c is not None for c in row):
                        rows.append([str(c) if c is not None else "" for c in row])
                sheets.append({"name": sheet_name, "rows": rows[:200]})
            return {
                "type": "spreadsheet",
                "filename": target.name,
                "sheets": sheets
            }
        except Exception:
            pass

        # Fallback to zero-dependency zipfile + xml parser
        try:
            import zipfile, xml.etree.ElementTree as ET
            with zipfile.ZipFile(target) as z:
                shared_strings = []
                if "xl/sharedStrings.xml" in z.namelist():
                    tree = ET.fromstring(z.read("xl/sharedStrings.xml"))
                    for si in tree.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si") or tree.findall(".//si"):
                        t = si.find(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t") or si.find(".//t")
                        shared_strings.append(t.text if t is not None and t.text else "")

                rows = []
                if "xl/worksheets/sheet1.xml" in z.namelist():
                    tree = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
                    ns = {"ns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                    for r in tree.findall(".//ns:row", ns) or tree.findall(".//row"):
                        row_vals = []
                        for c in r.findall("./ns:c", ns) or r.findall("./c"):
                            v = c.find("./ns:v", ns) or c.find("./v")
                            val = v.text if v is not None and v.text else ""
                            if c.attrib.get("t") == "s" and val.isdigit():
                                idx = int(val)
                                if idx < len(shared_strings):
                                    val = shared_strings[idx]
                            row_vals.append(val)
                        rows.append(row_vals)
                return {
                    "type": "spreadsheet",
                    "filename": target.name,
                    "sheets": [{"name": "Sheet1", "rows": rows[:200]}]
                }
        except Exception as e:
            return {"type": "error", "error": f"Failed to parse xlsx: {str(e)}"}
    return {"type": "unknown"}

class AgentHttpHandler(BaseHTTPRequestHandler):
    runner: AgentRunner
    connector_manager: ConnectorManager

    def _json(self, status: int, data: Any):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Static assets
        if path in ("/", "/index.html"):
            self._serve_static_file("index.html", "text/html")
            return
        elif path == "/styles.css":
            self._serve_static_file("styles.css", "text/css")
            return
        elif path == "/app.js":
            self._serve_static_file("app.js", "application/javascript")
            return

        # API Routes
        if path == "/api/sessions":
            sessions = list_sessions()
            self._json(200, {"sessions": sessions})
            return

        elif path.startswith("/api/sessions/"):
            session_id = path.removeprefix("/api/sessions/")
            session = get_session(session_id)
            if not session:
                self._json(404, {"error": "Session not found"})
                return
            messages = get_messages(session_id)
            artifacts = list_artifacts(session_id)
            self._json(200, {"session": session, "messages": messages, "artifacts": artifacts})
            return

        elif path == "/api/connectors":
            summary = self.connector_manager.get_all_connectors_summary()
            self._json(200, {"connectors": summary})
            return

        elif path.startswith("/api/workspace/"):
            parts = [p for p in path.split("/") if p]
            # Expected format: ['api', 'workspace', '<session_id>', 'files' | 'file']
            if len(parts) >= 4 and parts[3] == "files":
                session_id = parts[2]
                sbx = SessionSandbox(session_id)
                files = []
                for rel, meta in snapshot_workspace(sbx.workspace_dir).items():
                    files.append({
                        "name": Path(rel).name,
                        "rel_path": rel,
                        "size": meta["size"],
                        "mtime": meta["mtime"],
                    })
                self._json(200, {"files": sorted(files, key=lambda x: x["name"])})
                return

            elif len(parts) >= 4 and parts[3] == "file":
                # Download or preview workspace file
                session_id = parts[2]
                rel_path = query.get("path", [""])[0]
                if not rel_path or ".." in rel_path:
                    self._json(400, {"error": "Invalid file path"})
                    return
                sbx = SessionSandbox(session_id)
                target = (sbx.workspace_dir / rel_path).resolve()
                if not target.is_file() or not target.is_relative_to(sbx.workspace_dir):
                    self._json(404, {"error": "File not found"})
                    return

                content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                data = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Content-Disposition", f'inline; filename="{target.name}"')
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                self.wfile.write(data)
                return

            elif len(parts) >= 4 and parts[3] == "preview":
                session_id = parts[2]
                rel_path = query.get("path", [""])[0]
                if not rel_path or ".." in rel_path:
                    self._json(400, {"error": "Invalid file path"})
                    return
                sbx = SessionSandbox(session_id)
                target = (sbx.workspace_dir / rel_path).resolve()
                if not target.is_file() or not target.is_relative_to(sbx.workspace_dir):
                    self._json(404, {"error": "File not found"})
                    return

                ext = target.suffix.lower()
                if ext in (".xlsx", ".xlsm", ".csv", ".tsv"):
                    sheet_data = parse_spreadsheet_data(target)
                    self._json(200, sheet_data)
                    return
                elif ext == ".pdf":
                    self._json(200, {
                        "type": "pdf",
                        "filename": target.name,
                        "size": target.stat().st_size,
                        "file_url": f"/api/workspace/{session_id}/file?path={urllib.parse.quote(rel_path)}",
                    })
                    return
                elif ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"):
                    self._json(200, {
                        "type": "image",
                        "filename": target.name,
                        "file_url": f"/api/workspace/{session_id}/file?path={urllib.parse.quote(rel_path)}",
                    })
                    return
                else:
                    try:
                        text_content = target.read_text(encoding="utf-8", errors="replace")
                        self._json(200, {
                            "type": "text",
                            "filename": target.name,
                            "content": text_content,
                        })
                    except Exception as e:
                        self._json(500, {"error": str(e)})
                    return

            elif len(parts) >= 4 and parts[3] == "zip":
                # Download full session workspace as ZIP
                session_id = parts[2]
                sbx = SessionSandbox(session_id)
                import io, zipfile
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for root, dirs, files in os.walk(sbx.workspace_dir):
                        for file in files:
                            if file.startswith("."):
                                continue
                            full_p = Path(root) / file
                            rel_p = full_p.relative_to(sbx.workspace_dir)
                            zf.write(full_p, str(rel_p))
                buf.seek(0)
                zip_data = buf.getvalue()
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", str(len(zip_data)))
                self.send_header("Content-Disposition", f'attachment; filename="workspace_{session_id[:8]}.zip"')
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(zip_data)
                return

        self._json(404, {"error": "Endpoint not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json()

        if path == "/api/sessions":
            title = body.get("title", "New chat")
            session = create_session(title=title)
            self._json(201, {"session": session})
            return

        elif path == "/api/chat":
            session_id = body.get("session_id")
            text = (body.get("text") or "").strip()
            if not session_id or not text:
                self._json(400, {"error": "session_id and text are required"})
                return

            is_stream = body.get("stream", True)
            if is_stream:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                def sse_callback(event_type: str, data: dict):
                    msg = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
                    try:
                        self.wfile.write(msg.encode("utf-8"))
                        self.wfile.flush()
                    except Exception:
                        pass

                try:
                    self.runner.run_turn(session_id, text, callback=sse_callback)
                except Exception as exc:
                    sse_callback("error", {
                        "title": "Turn Execution Error",
                        "message": str(exc),
                        "remedy": "Check the terminal logs on Termux.",
                        "raw": str(exc),
                    })
                self.close_connection = True
                return
            else:
                try:
                    outcome = self.runner.run_turn(session_id, text)
                    self._json(200, outcome)
                except Exception as e:
                    self._json(500, {"error": f"Agent error: {str(e)}"})
                return

        elif path.startswith("/api/connectors/") and path.endswith("/toggle"):
            cid = path.split("/")[3]
            enabled = body.get("enabled")
            new_state = toggle_connector(cid, enabled)
            self._json(200, {"id": cid, "enabled": new_state})
            return

        elif path.startswith("/api/connectors/") and path.endswith("/config"):
            cid = path.split("/")[3]
            config = body.get("config", {})
            upsert_connector(
                connector_id=cid,
                name=body.get("name", cid.capitalize()),
                kind=body.get("kind", "builtin"),
                description=body.get("description", ""),
                config=config,
                enabled=1,
            )
            self._json(200, {"success": True, "id": cid})
            return

        elif path == "/api/connectors/custom_mcp":
            name = body.get("name", "Custom MCP")
            kind = body.get("kind", "mcp_stdio")
            description = body.get("description", "Custom MCP Connector")
            config = body.get("config", {})
            cid = f"mcp_{name.lower().replace(' ', '_')}"

            upsert_connector(
                connector_id=cid,
                name=name,
                kind=kind,
                description=description,
                config=config,
                enabled=1,
            )
            self._json(201, {"success": True, "id": cid})
            return

        self._json(404, {"error": "Endpoint not found"})

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/sessions":
            count = clear_all_sessions()
            self._json(200, {"deleted_count": count})
            return

        elif path.startswith("/api/sessions/"):
            session_id = path.removeprefix("/api/sessions/")
            success = delete_session(session_id)
            if success:
                self._json(200, {"success": True, "id": session_id})
            else:
                self._json(404, {"error": "Session not found"})
            return

        elif path.startswith("/api/connectors/"):
            cid = path.removeprefix("/api/connectors/")
            success = delete_connector(cid)
            self._json(200, {"success": success, "id": cid})
            return

        self._json(404, {"error": "Endpoint not found"})

    def _serve_static_file(self, filename: str, content_type: str):
        filepath = STATIC_DIR / filename
        if not filepath.is_file():
            self._json(404, {"error": f"Static file {filename} not found"})
            return
        data = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

def run_server():
    init_db()
    connector_manager = ConnectorManager()
    runner = AgentRunner(connector_manager=connector_manager)

    AgentHttpHandler.runner = runner
    AgentHttpHandler.connector_manager = connector_manager

    server = ThreadingHTTPServer((HOST, PORT), AgentHttpHandler)
    print(f"🚀 Termux Agent running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()
