"""HTTP Web Server for Termux Agent."""

import json
import mimetypes
import os
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from config import HOST, PORT, MAX_UPLOAD_BYTES, WORKSPACES_DIR
from db import (
    init_db,
    get_skill_states,
    set_skill_enabled,
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
import vision as vision_mod
from config import LLM_MODEL, MAX_UPLOAD_BYTES, SKILL_ROUTER
from skills import (
    SkillError,
    SkillRegistry,
    SkillRouter,
    create_skill,
    delete_skill,
    update_skill,
)
from uploads import UploadError, parse_multipart, store_uploads
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
    skill_registry: SkillRegistry

    def _json(self, status: int, data: Any):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        """Read the request body exactly once (JSON *or* multipart)."""
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _read_json(self, raw: bytes | None = None) -> dict:
        if raw is None:
            raw = self._read_body()
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Static assets (the React console: index.html + app.js + app.css)
        if self._try_serve_static(path):
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

        elif path == "/api/skills":
            states = get_skill_states()
            skills = [
                skill.to_dict(
                    enabled=states.get(name, {}).get("enabled", True),
                    runs=states.get(name, {}).get("runs", 0),
                    last_used=states.get(name, {}).get("last_used"),
                )
                for name, skill in sorted(self.skill_registry.all().items())
            ]
            self._json(200, {"skills": skills})
            return

        elif path == "/api/config":
            # What the console needs to know about the agent's capabilities.
            self._json(200, {
                "model": LLM_MODEL,
                "vision": vision_mod.model_has_vision(LLM_MODEL),
                "skill_router": SKILL_ROUTER,
                "max_upload_mb": max(1, MAX_UPLOAD_BYTES // (1024 * 1024)),
            })
            return

        elif path == "/api/skills/router":
            # Preview what the router would load for a message — used by the UI
            # so the routing rules are inspectable instead of magic.
            query = urllib.parse.parse_qs(parsed.query).get("q", [""])[0]
            files = urllib.parse.parse_qs(parsed.query).get("file", [])
            states = {n: st["enabled"] for n, st in get_skill_states().items()}
            matches = SkillRouter(self.skill_registry).route(query, files, states)
            self._json(200, {"query": query, "files": files, "matches": matches})
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
        raw_body = self._read_body()
        body = self._read_json(raw_body)

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

            attachments = body.get("attachments") or []
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
                    self.runner.run_turn(
                        session_id, text, callback=sse_callback, attachments=attachments
                    )
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
                    outcome = self.runner.run_turn(session_id, text, attachments=attachments)
                    self._json(200, outcome)
                except Exception as e:
                    self._json(500, {"error": f"Agent error: {str(e)}"})
                return

        elif path.startswith("/api/workspace/") and path.endswith("/upload"):
            parts = [p for p in path.split("/") if p]
            # /api/workspace/<session_id>/upload
            if len(parts) != 4:
                self._json(404, {"error": "Endpoint not found"})
                return
            session_id = parts[2]
            if not get_session(session_id):
                self._json(404, {"error": "Session not found"})
                return

            if not raw_body:
                self._json(400, {"error": "Empty upload."})
                return
            if len(raw_body) > MAX_UPLOAD_BYTES * 4:
                self._json(
                    413,
                    {"error": f"Upload exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit."},
                )
                return

            raw = raw_body
            try:
                parsed = parse_multipart(self.headers.get("Content-Type", ""), raw)
                sandbox = SessionSandbox(session_id)
                stored = store_uploads(sandbox.workspace_dir, parsed)
            except UploadError as exc:
                self._json(400, {"error": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": f"Upload failed: {exc}"})
                return

            self._json(201, {"files": stored})
            return

        elif path == "/api/skills":
            try:
                skill = create_skill(
                    name=str(body.get("name", "")),
                    title=str(body.get("title", "") or ""),
                    description=str(body.get("description", "")),
                    when_to_use=str(body.get("when_to_use", "") or ""),
                    triggers=body.get("triggers") or [],
                    files=body.get("files") or [],
                    uses=body.get("uses") or [],
                    body=str(body.get("body", "")),
                    icon=str(body.get("icon", "spark") or "spark"),
                    author="user",
                    overwrite=bool(body.get("overwrite")),
                )
            except SkillError as exc:
                self._json(400, {"error": str(exc)})
                return
            self._json(201, {"skill": skill.to_dict()})
            return

        elif path.startswith("/api/skills/") and path.endswith("/toggle"):
            name = path.split("/")[3]
            enabled = body.get("enabled")
            if enabled is None:
                enabled = not get_skill_states().get(name, {}).get("enabled", True)
            set_skill_enabled(name, bool(enabled))
            self._json(200, {"id": name, "enabled": bool(enabled)})
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

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        raw_body = self._read_body()

        if path.startswith("/api/skills/"):
            name = path.removeprefix("/api/skills/")
            body = self._read_json(raw_body or b"{}")
            try:
                skill = update_skill(name, **{k: v for k, v in body.items() if k in {
                    "title", "description", "when_to_use", "uses", "triggers",
                    "files", "body", "icon",
                }})
            except SkillError as exc:
                self._json(400, {"error": str(exc)})
                return
            self._json(200, {"skill": skill.to_dict()})
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

        elif path.startswith("/api/skills/"):
            name = path.removeprefix("/api/skills/")
            try:
                delete_skill(name)
            except SkillError as exc:
                self._json(400, {"error": str(exc)})
                return
            self._json(200, {"success": True, "id": name})
            return

        elif path.startswith("/api/connectors/"):
            cid = path.removeprefix("/api/connectors/")
            success = delete_connector(cid)
            self._json(200, {"success": success, "id": cid})
            return

        self._json(404, {"error": "Endpoint not found"})

    def _try_serve_static(self, path: str) -> bool:
        """Serve anything inside web/static (the built console), traversal-safe.

        Returns True when the request was handled. `/` maps to index.html.
        """
        rel = urllib.parse.unquote(path).lstrip("/") or "index.html"
        if rel.endswith("/"):
            rel += "index.html"
        if ".." in rel or rel.startswith("."):
            return False

        target = (STATIC_DIR / rel).resolve()
        if not target.is_file() or not target.is_relative_to(STATIC_DIR):
            return False

        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in ("application/javascript", "application/json"):
            content_type = f"{content_type}; charset=utf-8"

        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)
        return True

def run_server():
    init_db()
    connector_manager = ConnectorManager()
    runner = AgentRunner(connector_manager=connector_manager)
    skill_registry = SkillRegistry()

    AgentHttpHandler.runner = runner
    AgentHttpHandler.connector_manager = connector_manager
    AgentHttpHandler.skill_registry = skill_registry

    server = ThreadingHTTPServer((HOST, PORT), AgentHttpHandler)
    print(f"🚀 Termux Agent running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()
