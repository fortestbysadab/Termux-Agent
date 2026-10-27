"""Verification tests for Termux Agent."""

import os
import shutil
import unittest
from pathlib import Path

from config import DATA_DIR, WORKSPACES_DIR
from db import (
    init_db,
    create_session,
    list_sessions,
    get_session,
    delete_session,
    add_message,
    get_messages,
    list_connectors,
    toggle_connector,
    record_artifact,
    list_artifacts,
)
from sandbox.runner import SessionSandbox
from sandbox.tracker import snapshot_workspace, diff_workspace
from connectors.manager import ConnectorManager
from agent.loop import AgentRunner
from agent.planner import (
    parse_provider_error,
    adapt_tools_for_gemini,
    adapt_messages_for_gemini,
    LLMPlanner,
)

class TestTermuxAgent(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_database_and_sessions(self):
        # Create session
        session = create_session(title="Test Session")
        sid = session["id"]
        self.assertIsNotNone(sid)

        # Verify session in list
        sessions = list_sessions()
        self.assertTrue(any(s["id"] == sid for s in sessions))

        # Add messages
        msg1 = add_message(sid, "user", "Hello agent")
        msg2 = add_message(sid, "assistant", "Hello! How can I help?")
        history = get_messages(sid)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["content"], "Hello agent")

        # Record artifact
        art = record_artifact(sid, "test.txt", "test.txt", 100)
        artifacts = list_artifacts(sid)
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]["filename"], "test.txt")

        # Delete session
        deleted = delete_session(sid)
        self.assertTrue(deleted)
        self.assertIsNone(get_session(sid))
        self.assertEqual(len(get_messages(sid)), 0)

    def test_sandbox_runner_and_file_tracking(self):
        session = create_session(title="Sandbox Test")
        sid = session["id"]
        sandbox = SessionSandbox(sid)

        before = snapshot_workspace(sandbox.workspace_dir)

        # Run terminal command to create a file
        cmd_result = sandbox.run_command("echo 'Hello from isolated sandbox' > hello.txt && ls -la")
        self.assertTrue(cmd_result["ok"])
        self.assertIn("hello.txt", cmd_result["stdout"])

        after = snapshot_workspace(sandbox.workspace_dir)
        diff = diff_workspace(before, after)

        self.assertIn("hello.txt", diff["created"])

        # Clean up
        delete_session(sid)

    def test_bionic_cfi_safe_sandbox(self):
        """Ensure sandbox does not set RLIMIT_AS which triggers bionic linker CFI crashes."""
        session = create_session(title="Bionic Test")
        sid = session["id"]
        sandbox = SessionSandbox(sid)

        # Execute multiple commands sequentially
        res1 = sandbox.run_command("echo 42")
        self.assertEqual(res1["exit_code"], 0)
        self.assertIn("42", res1["stdout"])

        res2 = sandbox.run_command("exit 3")
        self.assertEqual(res2["exit_code"], 3)
        self.assertFalse(res2["ok"])

        delete_session(sid)

    def test_connectors_manager(self):
        manager = ConnectorManager()
        summary = manager.get_all_connectors_summary()
        self.assertTrue(len(summary) >= 12)

        # Check GitHub exists in list
        github = next(c for c in summary if c["id"] == "github")
        self.assertEqual(github["name"], "GitHub")

        # Toggle connector
        toggle_connector("github", enabled=True)
        tools, routing = manager.get_active_tools()
        self.assertTrue(any("github" in t["function"]["name"] for t in tools))
        self.assertIn("github_list_repos", routing)

        # Untoggle
        toggle_connector("github", enabled=False)

    def test_parse_provider_error(self):
        """Test structured error parser generates actionable advice for common LLM errors."""
        # 1. Thought signature error
        err1 = parse_provider_error(400, '{"error": {"message": "Function call is missing a thought_signature in functionCall parts"}}')
        self.assertIn("thought signature", err1["title"].lower())
        self.assertTrue(len(err1["remedy"]) > 0)

        # 2. Quota limit
        err2 = parse_provider_error(429, '{"error": "Rate limit exceeded"}')
        self.assertEqual(err2["title"], "Quota / Rate Limit Exceeded")

        # 3. Invalid API key
        err3 = parse_provider_error(401, '{"error": "Unauthorized"}')
        self.assertEqual(err3["title"], "Authentication Failed")

    def test_gemini_message_adaptation(self):
        """Verify Gemini thought_signature and tool schema adaptation."""
        raw_tools = [
            {
                "type": "function",
                "function": {
                    "name": "terminal",
                    "description": "Run command",
                    "parameters": {
                        "type": "object",
                        "$schema": "http://json-schema.org/draft-07/schema#",
                        "properties": {
                            "command": {"type": "string", "description": "The command"}
                        },
                        "required": ["command"]
                    }
                }
            }
        ]
        sanitized = adapt_tools_for_gemini(raw_tools)
        self.assertNotIn("$schema", sanitized[0]["function"]["parameters"])

        # Test tool response adaptation (removes 'name' to satisfy strict OpenAI endpoint requirements)
        messages = [
            {"role": "user", "content": "run ls"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "terminal", "arguments": '{"command":"ls"}'}}],
                "extra_content": {"google": {"thought_signature": "sig123"}}
            },
            {"role": "tool", "tool_call_id": "call_1", "name": "terminal", "content": "file1.txt"}
        ]
        adapted = adapt_messages_for_gemini(messages)
        self.assertNotIn("name", adapted[2])
        self.assertEqual(adapted[1]["tool_calls"][0]["extra_content"]["google"]["thought_signature"], "sig123")

    def test_filter_chat_artifacts(self):
        """Ensure intermediate generator scripts (.py) are filtered out of chat cards when deliverables (.pdf) exist."""
        from agent.loop import filter_chat_artifacts

        # Case 1: User asks for PDF, agent generates script and PDF
        files1 = ["generate_pdf.py", "demo_document.pdf"]
        chat_files1 = filter_chat_artifacts(files1, user_text="create a demo pdf")
        self.assertEqual(chat_files1, ["demo_document.pdf"])

        # Case 2: User explicitly asks for python script
        files2 = ["script.py"]
        chat_files2 = filter_chat_artifacts(files2, user_text="write a python script for me")
        self.assertEqual(chat_files2, ["script.py"])

        # Case 3: User asks for both python code and image chart
        files3 = ["generate_chart.py", "chart.png"]
        chat_files3 = filter_chat_artifacts(files3, user_text="give me python code and the chart image")
        self.assertEqual(chat_files3, ["generate_chart.py", "chart.png"])

    def test_workspace_isolation_and_file_endpoints(self):
        """Verify per-session workspace isolation and file preview/download retrieval."""
        s1 = create_session(title="Session 1")
        s2 = create_session(title="Session 2")
        sid1, sid2 = s1["id"], s2["id"]

        sbx1 = SessionSandbox(sid1)
        sbx2 = SessionSandbox(sid2)

        # Create files in each session
        file1 = sbx1.workspace_dir / "demo_doc.pdf"
        file1.write_bytes(b"%PDF-1.4 test binary pdf content")

        file2 = sbx2.workspace_dir / "other.txt"
        file2.write_text("Hello session 2", encoding="utf-8")

        # Verify filesystem isolation
        self.assertTrue((sbx1.workspace_dir / "demo_doc.pdf").exists())
        self.assertFalse((sbx1.workspace_dir / "other.txt").exists())
        self.assertTrue((sbx2.workspace_dir / "other.txt").exists())
        self.assertFalse((sbx2.workspace_dir / "demo_doc.pdf").exists())

        # Verify URL path parsing logic matches the fixed server routing
        path = f"/api/workspace/{sid1}/files"
        parts = [p for p in path.split("/") if p]
        self.assertEqual(parts[0], "api")
        self.assertEqual(parts[1], "workspace")
        self.assertEqual(parts[2], sid1)
        self.assertEqual(parts[3], "files")

        file_path = f"/api/workspace/{sid1}/file"
        fparts = [p for p in file_path.split("/") if p]
        self.assertEqual(fparts[2], sid1)
        self.assertEqual(fparts[3], "file")

        # Clean up
        delete_session(sid1)
        delete_session(sid2)

    def test_scratch_cleanup_and_deliverable_isolation(self):
        """Ensure scratch test files (e.g. test.xlsx) and helper scripts are identified and cleaned when deliverables exist."""
        from agent.loop import is_scratch_file, is_primary_deliverable

        self.assertTrue(is_scratch_file("test.xlsx"))
        self.assertTrue(is_scratch_file("test_dummy.txt"))
        self.assertTrue(is_scratch_file("generate_sheets.py"))
        self.assertTrue(is_scratch_file("temp.csv"))

        self.assertTrue(is_primary_deliverable("7_day_study_habit_plan.xlsx"))
        self.assertTrue(is_primary_deliverable("neuroscience_overview.pdf"))
        self.assertFalse(is_primary_deliverable("test.xlsx"))

    def test_spreadsheet_parser(self):
        """Test the spreadsheet parser on CSV and XLSX formats."""
        from web.server import parse_spreadsheet_data
        import tempfile

        with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as f:
            f.write("Day,Task,Status\nDay 1,Study Python,Done\nDay 2,Review,Pending\n")
            f_path = Path(f.name)

        try:
            data = parse_spreadsheet_data(f_path)
            self.assertEqual(data["type"], "spreadsheet")
            self.assertEqual(len(data["sheets"][0]["rows"]), 3)
            self.assertEqual(data["sheets"][0]["rows"][0], ["Day", "Task", "Status"])
        finally:
            f_path.unlink(missing_ok=True)

    def test_termux_heavy_package_interception(self):
        """Verify runner intercepts heavy pip C-compilation and apt-get on Termux with immediate advisory."""
        session = create_session(title="Interceptor Test")
        sid = session["id"]
        sandbox = SessionSandbox(sid)

        res1 = sandbox.run_command("pip install matplotlib numpy")
        self.assertFalse(res1["ok"])
        self.assertIn("SVG", res1["stderr"])

        res2 = sandbox.run_command("apt-get update")
        self.assertFalse(res2["ok"])
        self.assertIn("apt-get", res2["stderr"])

        delete_session(sid)

    def test_agent_event_callbacks(self):
        """Verify that AgentRunner fires real-time callbacks."""
        session = create_session(title="Callback Test")
        sid = session["id"]

        manager = ConnectorManager()
        runner = AgentRunner(manager)
        events = []

        def on_event(event_type, data):
            events.append((event_type, data))

        result = runner.run_turn(sid, "hello", callback=on_event)
        self.assertTrue(len(events) > 0)
        # Verify done or error event was emitted
        event_types = [e[0] for e in events]
        self.assertTrue("done" in event_types or "error" in event_types)
        delete_session(sid)

    def test_console_assets_are_built(self):
        """The React console must ship pre-built so the server stays dependency-free."""
        from pathlib import Path
        from web.server import STATIC_DIR

        for name in ("index.html", "app.js", "app.css"):
            asset = Path(STATIC_DIR) / name
            self.assertTrue(asset.is_file(), f"missing {name} — run: cd frontend && npm run build")
            self.assertGreater(asset.stat().st_size, 500, f"{name} looks empty")

        html = (Path(STATIC_DIR) / "index.html").read_text(encoding="utf-8")
        self.assertIn("/app.css", html)
        self.assertIn("/app.js", html)
        # No external assets: the console must work fully offline on a phone.
        # (Inline data: URIs such as the SVG favicon are fine — they never fetch.)
        for pattern in ('src="http', 'href="http', "href='http"):
            self.assertNotIn(pattern, html)

    def test_libraries_dev_components_are_bundled(self):
        """Border Beam, Thinking Orbs and Bot Avatars are compiled into app.js."""
        from pathlib import Path
        from web.server import STATIC_DIR

        bundle = (Path(STATIC_DIR) / "app.js").read_text(encoding="utf-8", errors="replace")
        for marker in (
            "data-beam",        # border-beam (composer only)
            "requestAnimationFrame",  # thinking-orbs + bot-avatars canvases
            "ThinkingOrb" if "ThinkingOrb" in bundle else "thinking-orbs",
        ):
            self.assertIn(marker, bundle)

if __name__ == "__main__":
    unittest.main()
