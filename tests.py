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

if __name__ == "__main__":
    unittest.main()
