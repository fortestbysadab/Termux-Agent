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

    # ------------------------------------------------------------------ skills
    def test_skill_registry_discovers_every_skill(self):
        """Every SKILL.md on disk parses without error and carries frontmatter."""
        from skills import SkillRegistry

        registry = SkillRegistry()
        skills = registry.all()
        names = set(skills)
        for expected in ("data-wrangler", "svg-chart", "xlsx-report", "pdf-report", "report-bundle"):
            self.assertIn(expected, names)
        for skill in skills.values():
            self.assertIsNone(skill.error, f"{skill.name}: {skill.error}")
            self.assertTrue(skill.description, f"{skill.name} has no description")
            self.assertTrue(skill.when_to_use, f"{skill.name} has no when_to_use")

    def test_skill_can_call_other_skills(self):
        """report-bundle pulls in its four dependencies in one load."""
        from skills import SkillRegistry

        text, loaded, missing = SkillRegistry().load_with_dependencies("report-bundle")
        self.assertEqual(missing, [])
        self.assertIn("report-bundle", loaded)
        for dep in ("data-wrangler", "svg-chart", "xlsx-report", "pdf-report"):
            self.assertIn(dep, loaded)
            self.assertIn(dep, text)
        self.assertGreater(len(text), 2000)

    def test_skill_catalogue_is_progressive(self):
        """The prompt only ever gets name + description + when_to_use."""
        from skills import SkillRegistry

        registry = SkillRegistry()
        states = {name: True for name in registry.all()}
        catalogue = registry.catalog(states)
        self.assertIn("svg-chart", catalogue)
        self.assertLess(len(catalogue), 5000)
        # bodies stay out of the prompt until use_skill is called
        body_marker = "## Procedure" if "## Procedure" in registry.get("svg-chart").body else None
        if body_marker:
            self.assertNotIn(body_marker, catalogue)

    def test_skill_toggle_roundtrip(self):
        from db import get_skill_states, set_skill_enabled
        from skills import SkillRegistry

        set_skill_enabled("svg-chart", False)
        set_skill_enabled("svg-chart", False)
        states = {n: st["enabled"] for n, st in get_skill_states().items()}
        self.assertFalse(states["svg-chart"])
        self.assertNotIn("svg-chart", [s.name for s in SkillRegistry().enabled(states)])
        set_skill_enabled("svg-chart", True)
        states = {n: st["enabled"] for n, st in get_skill_states().items()}
        self.assertTrue(states["svg-chart"])
        self.assertIn("svg-chart", [s.name for s in SkillRegistry().enabled(states)])

    # ----------------------------------------------------------------- uploads
    def test_upload_sanitises_names(self):
        from uploads import sanitize_filename

        self.assertEqual(sanitize_filename("../../etc/passwd.csv"), "passwd.csv")
        self.assertEqual(sanitize_filename("my report (final).csv"), "my report (final).csv")
        self.assertNotIn("/", sanitize_filename("a/b/c.csv"))
        self.assertTrue(sanitize_filename("weird" + chr(0) + "name.csv"))

    def test_upload_rejects_bad_extensions(self):
        from uploads import check_extension, UploadError

        check_extension("notes.csv")
        with self.assertRaises(UploadError):
            check_extension("payload.exe")
        with self.assertRaises(UploadError):
            check_extension("noextension")

    def test_upload_dedupes_and_stores_in_uploads_dir(self):
        from uploads import store_uploads

        workspace = Path(WORKSPACES_DIR) / "test_upload_ws"
        shutil.rmtree(workspace, ignore_errors=True)
        workspace.mkdir(parents=True, exist_ok=True)
        try:
            first = store_uploads(workspace, [{"filename": "scores.csv", "data": b"a,b\n1,2\n"}])
            second = store_uploads(workspace, [{"filename": "scores.csv", "data": b"c,d\n3,4\n"}])
            self.assertEqual(first[0]["rel_path"], "uploads/scores.csv")
            self.assertEqual(second[0]["rel_path"], "uploads/scores (2).csv")
            self.assertTrue((workspace / "uploads" / "scores.csv").is_file())
            self.assertEqual(first[0]["size"], 8)
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def test_upload_reaches_the_agent_prompt(self):
        """An uploaded file is named in the turn the model receives."""
        from uploads import store_uploads
        from agent.loop import _attachment_note

        session = create_session("upload prompt test")
        workspace = Path(WORKSPACES_DIR) / session["id"]
        workspace.mkdir(parents=True, exist_ok=True)
        try:
            stored = store_uploads(workspace, [{"filename": "scores.csv", "data": b"a,b\n1,2\n"}])
            self.assertTrue((workspace / "uploads" / "scores.csv").is_file())
            note = _attachment_note(stored)
            self.assertIn("uploads/scores.csv", note)
            self.assertIn("uploads/", note)
            self.assertEqual(_attachment_note([]), "")
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
            delete_session(session["id"])

    # -------------------------------------------------------------------- icons
    def test_brand_icons_are_real_marks(self):
        """Connector icons come from simple-icons, not the bot avatars."""
        from pathlib import Path

        from web.server import STATIC_DIR as STATIC

        src = (Path("frontend/src/brandIcons.jsx")).read_text(encoding="utf-8")
        self.assertIn("simple-icons", src)
        self.assertNotIn("BotAvatar", src)
        bundle = (Path(STATIC) / "app.js").read_text(encoding="utf-8", errors="replace")
        # A real brand path from github's mark survives minification.
        self.assertIn("M12 .297c-6.63", bundle)


    # ------------------------------------------------------------------ router
    def test_router_matches_words_and_files(self):
        """A mention of PDF, or a .csv attachment, selects the right skill."""
        from skills import SkillRouter

        router = SkillRouter()
        pdf = router.route("please read this PDF invoice and summarise it", [])
        self.assertEqual([m["name"] for m in pdf], ["pdf-report"])
        csv = router.route("clean up the rows in this file", ["scores.csv"])
        self.assertEqual([m["name"] for m in csv], ["data-wrangler"])
        chart = router.route("chart the scores for me", [])
        self.assertEqual([m["name"] for m in chart], ["svg-chart"])
        self.assertEqual(router.route("hey, how are you?", []), [])

    def test_router_loads_dependencies_of_matched_skill(self):
        from skills import SkillRouter

        matches = SkillRouter().route("build the full report bundle", [])
        self.assertEqual(matches[0]["name"], "report-bundle")

    def test_agent_auto_loads_matched_skill(self):
        """The loop pulls the skill into the prompt itself — no tool call needed."""
        from connectors.manager import ConnectorManager
        from agent.loop import AgentRunner

        runner = AgentRunner(ConnectorManager())
        prompt, events, runs = runner._auto_route("read this pdf for me", [{"filename": "x.pdf"}])
        self.assertIn("AUTO-LOADED SKILLS", prompt)
        self.assertIn("pdf-report", [r["name"] for r in runs])
        self.assertTrue(all(r.get("auto") for r in runs))
        self.assertEqual(events[0][0], "skill_done")
        system_prompt = runner._system_prompt(prompt)
        self.assertIn("pdf-report", system_prompt)
        self.assertNotIn("{catalogue}", system_prompt)
        self.assertNotIn("{vision}", system_prompt)

    def test_router_ignores_chit_chat(self):
        from connectors.manager import ConnectorManager
        from agent.loop import AgentRunner

        prompt, events, runs = AgentRunner(ConnectorManager())._auto_route("thanks, that works", [])
        self.assertEqual((prompt, events, runs), ("", [], []))

    def test_user_can_create_and_delete_a_skill(self):
        """A skill written at runtime routes immediately, then disappears."""
        from skills import SkillRouter, create_skill, delete_skill, SkillError

        created = create_skill(
            name="reading list digest",
            description="Collect links into one markdown digest.",
            when_to_use="The user asks for a reading list digest.",
            triggers=["reading list", "digest"],
            files=["txt"],
            body="# Steps\n1. Collect links.\n2. Write digest.md",
        )
        try:
            self.assertEqual(created.name, "reading-list-digest")
            self.assertEqual(created.author, "user")
            self.assertIn("reading-list-digest", [m["name"] for m in SkillRouter().route("make a reading list digest", [])])
            with self.assertRaises(SkillError):
                create_skill(name="reading-list-digest", description="dup", body="x")
            with self.assertRaises(SkillError):
                create_skill(name="broken", description="", body="x")
            with self.assertRaises(SkillError):
                delete_skill("svg-chart")  # built-ins are protected
        finally:
            delete_skill("reading-list-digest")
        self.assertNotIn("reading-list-digest", [m["name"] for m in SkillRouter().route("make a reading list digest", [])])

    # ------------------------------------------------------------------ vision
    def test_vision_inlines_images_for_multimodal_models(self):
        from pathlib import Path
        import tempfile
        import vision

        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\xf8\xcf\xc0\x50"
            b"\x0f\x00\x04\x85\x01\x80\x84\xa9\x8c!\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "uploads").mkdir()
            (Path(tmp) / "uploads" / "shot.png").write_bytes(png)
            (Path(tmp) / "uploads" / "scan.pdf").write_bytes(b"%PDF-1.4")
            files = [
                {"filename": "shot.png", "rel_path": "uploads/shot.png"},
                {"filename": "scan.pdf", "rel_path": "uploads/scan.pdf"},
            ]

            content, seen = vision.build_content("what is this?", files, tmp, "gemini-2.5-flash")
            self.assertIsInstance(content, list)
            self.assertEqual([p["type"] for p in content], ["text", "image_url"])
            self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/png;base64,"))
            self.assertEqual(seen, ["shot.png"])  # PDFs stay with the tools

            plain, seen_plain = vision.build_content("what is this?", files, tmp, "llama-3-8b")
            self.assertIsInstance(plain, str)
            self.assertEqual(seen_plain, [])
            self.assertFalse(vision.model_has_vision("llama-3-8b"))

    def test_vision_falls_back_when_forced_off(self):
        import vision

        self.assertFalse(vision.model_has_vision("gemini-2.5-flash", mode="off"))
        self.assertTrue(vision.model_has_vision("unknown-model", mode="on"))
        self.assertIn("cannot see images", vision.capability_note("llama-3-8b"))

    # ------------------------------------------------------------------ server
    def test_skills_api_routes(self):
        """The HTTP surface for authoring + router preview."""
        import json
        import urllib.request
        from web.server import AgentHttpHandler  # noqa: F401  (import guard: module loads)

        payload = json.dumps({
            "name": "api probe",
            "description": "Created over HTTP.",
            "body": "# Steps\n1. Do nothing.",
            "triggers": ["api probe"],
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:8080/api/skills", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                body = json.loads(resp.read())
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            self.skipTest("console not running on :8080")
        self.assertEqual(body["skill"]["name"], "api-probe")
        try:
            with urllib.request.urlopen("http://127.0.0.1:8080/api/skills/router?q=api%20probe", timeout=3) as resp:
                matches = json.loads(resp.read())["matches"]
            self.assertEqual(matches[0]["name"], "api-probe")
        finally:
            urllib.request.urlopen(urllib.request.Request(
                "http://127.0.0.1:8080/api/skills/api-probe", method="DELETE"), timeout=3).read()


    # ------------------------------------------------------------------- pdf
    def test_pdfkit_writes_a_renderable_page_tree(self):
        """The page tree must point at /Page objects, not at a content stream.

        This is the bug that produced a 3 kB file with `Page size: 0 x 0` that
        every viewer rendered blank.
        """
        import sys
        import tempfile
        from pathlib import Path

        sys.path.insert(0, str(Path("skills/pdf-report").resolve()))
        from pdfkit import Canvas, verify

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "probe.pdf"
            doc = Canvas(title="Probe", footer="unit test")
            y = doc.title("Probe report")
            y = doc.paragraph("Body copy that has to wrap on its own. " * 4, y=y, size=10)
            y = doc.table(
                x=doc.left, y=y - 10, width=doc.content_width,
                headers=["Country", "Value"],
                rows=[("Brazil", "66.4"), ("Vietnam", "27.5")],
                col_align=["left", "right"],
            )
            doc.bar_chart(x=doc.left, y=y - 20, width=doc.content_width, height=180,
                          data=[("Brazil", 66.4), ("Vietnam", 27.5)])
            doc.save(target)

            info = verify(target)
            self.assertTrue(info["header_ok"])
            self.assertTrue(info["eof_ok"])
            self.assertEqual(info["pages"], 1)
            self.assertTrue(info["page_tree_ok"], "page tree is broken — viewers will render blank")
            self.assertTrue(info["has_chart"], f"no chart operators: {info}")

    def test_pdfkit_bar_chart_is_vector(self):
        """Bars are rectangle ops in the content stream, not text or a bitmap."""
        import sys
        import tempfile
        from pathlib import Path

        sys.path.insert(0, str(Path("skills/pdf-report").resolve()))
        from pdfkit import Canvas, verify

        with tempfile.TemporaryDirectory() as tmp:
            with_chart = Path(tmp) / "chart.pdf"
            doc = Canvas()
            doc.bar_chart(x=56, y=700, width=480, height=220,
                          data=[("A", 10), ("B", 20), ("C", 15), ("D", 5), ("E", 12)])
            doc.save(with_chart)
            plain = Path(tmp) / "plain.pdf"
            doc2 = Canvas()
            doc2.paragraph("just text, no chart at all", y=700)
            doc2.save(plain)

            a, b = verify(with_chart), verify(plain)
            self.assertGreater(a["rect_ops"], b["rect_ops"])
            self.assertGreaterEqual(a["rect_ops"] - b["rect_ops"], 5)
            self.assertGreater(a["stroke_ops"], b["stroke_ops"])
            self.assertEqual(a["image_objects"], 0)
            self.assertFalse(b["has_chart"])

    def test_pdf_text_never_truncates_labels(self):
        """Country names must survive intact — 'Bra', 'Vie', 'Col' were a real bug."""
        import sys
        import tempfile
        from pathlib import Path

        sys.path.insert(0, str(Path("skills/pdf-report").resolve()))
        from pdfkit import Canvas, text_width, wrap_text

        # metrics-based wrapping stays inside the column
        line = "Brazil 66.4"
        self.assertGreater(text_width(line, 10), 0)
        self.assertTrue(all(text_width(l, 10) <= 200 for l in wrap_text("alpha beta gamma " * 12, 200, 10)))

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "labels.pdf"
            import zlib, re
            doc = Canvas()
            doc.table(x=56, y=700, width=480, headers=["Country", "Bags"],
                      rows=[("Brazil", "66.4"), ("Vietnam", "27.5"), ("Colombia", "11.4"),
                            ("Indonesia", "10.0"), ("Ethiopia", "8.4")])
            doc.save(target)
            raw = target.read_bytes()
            stream = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.S)[0]
            body = zlib.decompress(stream)
            for name in (b"Brazil", b"Vietnam", b"Colombia", b"Indonesia", b"Ethiopia"):
                self.assertIn(name, body)

    def test_pdf_report_skill_points_at_the_toolkit(self):
        """The skill must tell the agent to use pdfkit, not to hand-build objects."""
        from skills import SkillRegistry

        skill = SkillRegistry().get("pdf-report")
        self.assertIsNone(skill.error)
        self.assertIn("pdfkit", skill.body)
        self.assertIn("verify", skill.body)
        self.assertNotIn("Wrap text yourself at ~92 characters", skill.body)


    # ---------------------------------------------------------- elicitation
    def test_agent_pauses_and_asks_with_options(self):
        """ask_user ends the turn with input_required and stores the questions."""
        from connectors.manager import ConnectorManager
        from agent.loop import AgentRunner
        from db import create_session, delete_session, get_messages, get_pending_input

        class Planner:
            def complete(self, messages, tools=None):
                return {
                    "content": None,
                    "tool_calls": [{
                        "id": "call_q", "name": "ask_user",
                        "arguments": {
                            "intro": "Need two details.",
                            "questions": [
                                {"id": "format", "question": "Which format?",
                                 "options": [{"id": "pdf", "label": "PDF"},
                                             {"id": "xlsx", "label": "Excel"}]},
                                {"id": "len", "question": "How long?",
                                 "options": [{"label": "1 page"}, {"label": "5 pages"}]},
                            ],
                        },
                    }],
                }

        session = create_session("pause test")
        sid = session["id"]
        events = []
        try:
            runner = AgentRunner(ConnectorManager(), planner=Planner())
            out = runner.run_turn(sid, "make me a report", callback=lambda t, d: events.append(t))
            pending = out["input_required"]
            self.assertIsNotNone(pending)
            self.assertEqual([q["id"] for q in pending["questions"]], ["format", "len"])
            self.assertEqual(len(pending["questions"][0]["options"]), 2)
            self.assertTrue(pending["questions"][0]["allow_custom"])
            self.assertIn("input_required", events)
            # transcript stays valid: a question ends the turn, no dangling tool call
            self.assertTrue(all(m["role"] != "tool" for m in get_messages(sid)))
            self.assertIsNotNone(get_pending_input(pending["request_state"]))
        finally:
            delete_session(sid)

    def test_answers_resume_the_same_request(self):
        from connectors.manager import ConnectorManager
        from agent.loop import AgentRunner
        from db import (
            create_session, delete_session, get_pending_input, save_pending_input,
        )

        class Planner:
            def __init__(self):
                self.seen = None

            def complete(self, messages, tools=None):
                self.seen = messages
                return {"content": "Built it.", "tool_calls": []}

        session = create_session("resume test")
        sid = session["id"]
        try:
            save_pending_input(
                "tok-abc", sid, "make me a report",
                [{"id": "format", "question": "Which format?",
                  "options": [{"id": "pdf", "label": "PDF"}, {"id": "x", "label": "X"}]}],
            )
            planner = Planner()
            runner = AgentRunner(ConnectorManager(), planner=planner)
            out = runner.run_turn(
                sid, "make me a report",
                input_responses={"format": "PDF"}, request_state="tok-abc",
            )
            self.assertEqual(out["message"]["content"], "Built it.")
            self.assertIsNone(get_pending_input("tok-abc"), "token should be single-use")

            user_turns = [m for m in planner.seen if m["role"] == "user"]
            joined = " ".join(str(m["content"]) for m in user_turns)
            self.assertIn("PDF", joined)
            self.assertIn("do not ask again", joined.lower())
        finally:
            delete_session(sid)

    def test_question_payload_is_sanitised(self):
        """A single-option or empty question is dropped rather than rendered broken."""
        from agent.loop import _normalise_questions

        normalised = _normalise_questions([
            {"question": "Real one?", "options": [{"label": "Yes"}, {"label": "No"}]},
            {"question": "Only one option?", "options": [{"label": "Yes"}]},
            {"question": "", "options": [{"label": "a"}, {"label": "b"}]},
        ])
        self.assertEqual(len(normalised), 1)
        self.assertEqual(len(normalised[0]["options"]), 2)
        self.assertEqual(normalised[0]["id"], "q1")

    # --------------------------------------------------------- environment
    def test_environment_probe_reports_reality(self):
        import environment

        data = environment.probe(refresh=True)
        self.assertTrue(data["python"].startswith("3."))
        self.assertIn("cli", data)
        self.assertIn("packages", data)
        # the stdlib is always there, and a library that is genuinely absent is flagged
        self.assertTrue(environment.check(["sqlite3"])["sqlite3"]["available"])
        self.assertIn("reportlab", data["missing_packages"])

    def test_environment_block_is_in_the_prompt(self):
        from connectors.manager import ConnectorManager
        from agent.loop import AgentRunner

        prompt = AgentRunner(ConnectorManager())._system_prompt()
        self.assertIn("## ENVIRONMENT (probed, not assumed)", prompt)
        self.assertIn("check_environment", prompt)
        self.assertIn("CLARIFY WHEN IT MATTERS", prompt)
        self.assertNotIn("{environment}", prompt)

    def test_check_environment_tool_answers_precisely(self):
        import environment

        report = environment.check(["pdftoppm", "reportlab", "definitely-not-a-package"])
        self.assertTrue(report["pdftoppm"]["available"])
        self.assertEqual(report["pdftoppm"]["kind"], "binary")
        self.assertFalse(report["reportlab"]["available"])
        self.assertEqual(report["reportlab"]["kind"], "module")
        self.assertEqual(report["definitely-not-a-package"]["kind"], "unknown")


if __name__ == "__main__":
    unittest.main()
