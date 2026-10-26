"""ReAct Agent Execution Loop with Tool Calling, Terminal Sandbox, and Workspace Diffing."""

import json
import logging
from pathlib import Path
from typing import Any
from db import add_message, get_messages, record_artifact, update_session_title
from sandbox.runner import SessionSandbox
from sandbox.tracker import snapshot_workspace, diff_workspace
from connectors.manager import ConnectorManager
from agent.planner import LLMPlanner

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Termux Agent, a powerful AI assistant running inside a private environment on the user's Android/Linux device.

CAPABILITIES:
1. FULL TERMINAL ACCESS: You have access to `run_terminal_command`. You can run bash commands, install tools (pip, npm, apt), write scripts (Python, JS, C, Bash), process data, and inspect files.
2. ISOLATED WORKSPACE: Every session has an isolated workspace directory. All files, scripts, and output should be created in the current working directory.
3. CONNECTORS & MCP: You have access to any external tools from enabled Connectors (GitHub, Notion, Linear, etc.) and Custom MCP servers.

WORKFLOW RULES:
- If the user asks for a file (document, script, CSV, HTML, analysis, code), ALWAYS write/create the file in the workspace using terminal commands (e.g. `cat << 'EOF' > filename.ext ...` or Python scripts).
- If the task is purely conversational or an inquiry without file requests, answer directly in chat.
- After running terminal commands, explain the results clearly. Be concise, direct, and helpful.
"""

TERMINAL_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "run_terminal_command",
        "description": "Execute any Linux/Bash terminal command inside the session's isolated workspace. Use this to run scripts, create files, install packages, or process data.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The exact shell command to execute."
                }
            },
            "required": ["command"]
        }
    }
}

class AgentRunner:
    def __init__(self, connector_manager: ConnectorManager, planner: LLMPlanner = None):
        self.connectors = connector_manager
        self.planner = planner or LLMPlanner()

    def run_turn(self, session_id: str, user_text: str) -> dict[str, Any]:
        """Execute one complete conversational agent turn."""
        sandbox = SessionSandbox(session_id)

        # 1. Snapshot workspace before executing
        before_snap = snapshot_workspace(sandbox.workspace_dir)

        # 2. Retrieve history and active tools
        history = get_messages(session_id)
        active_tools, routing = self.connectors.get_active_tools()
        all_tools = [TERMINAL_TOOL_SCHEMA] + active_tools

        # 3. Assemble messages for LLM
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in history[-14:]:  # Keep recent context
            role = m["role"]
            content = m["content"] or ""
            if role == "user":
                messages.append({"role": "user", "content": content})
            elif role == "assistant":
                # If files were generated in previous turn, mention them to provide grounding
                if m.get("files_generated"):
                    files_note = f"\n(Files available in workspace: {', '.join(m['files_generated'])})"
                    content = content + files_note
                messages.append({"role": "assistant", "content": content})

        # Append new user message
        messages.append({"role": "user", "content": user_text})
        add_message(session_id, "user", user_text)

        # Auto-update session title on first turn
        if len(history) == 0:
            clean_title = " ".join(user_text.split()[:5])[:36]
            update_session_title(session_id, clean_title or "New Chat")

        # 4. Multi-turn Tool Calling Loop
        max_turns = 6
        collected_tool_runs = []
        final_text = ""

        for turn in range(max_turns):
            response = self.planner.complete(messages, tools=all_tools)
            content = response.get("content")
            tool_calls = response.get("tool_calls", [])

            if not tool_calls:
                final_text = content or "Task completed."
                break

            # Process tool calls
            assistant_msg = {"role": "assistant", "content": content or ""}
            formatted_tc = []
            for tc in tool_calls:
                formatted_tc.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])}
                })
            assistant_msg["tool_calls"] = formatted_tc
            messages.append(assistant_msg)

            for tc in tool_calls:
                t_name = tc["name"]
                t_args = tc["arguments"]

                if t_name == "run_terminal_command":
                    cmd = t_args.get("command", "")
                    exec_result = sandbox.run_command(cmd)
                    tool_content = f"STDOUT:\n{exec_result['stdout']}\nSTDERR:\n{exec_result['stderr']}\nExit Code: {exec_result['exit_code']}"
                    collected_tool_runs.append({
                        "tool": "terminal",
                        "command": cmd,
                        "stdout": exec_result["stdout"],
                        "stderr": exec_result["stderr"],
                        "exit_code": exec_result["exit_code"],
                        "duration_ms": exec_result["duration_ms"],
                        "ok": exec_result["ok"],
                    })
                else:
                    # Dispatch to Connector or MCP
                    res = self.connectors.execute_tool(t_name, t_args, routing)
                    tool_content = json.dumps(res) if isinstance(res, (dict, list)) else str(res)
                    collected_tool_runs.append({
                        "tool": t_name,
                        "arguments": t_args,
                        "result": res,
                        "ok": not ("error" in res if isinstance(res, dict) else False),
                    })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_content[:8000]
                })

        # 5. Snapshot workspace after turn to detect created or modified files
        after_snap = snapshot_workspace(sandbox.workspace_dir)
        changes = diff_workspace(before_snap, after_snap)
        changed_files = changes["all_changed"]

        # Record generated artifacts in database
        artifacts_meta = []
        for rel in changed_files:
            file_path = sandbox.workspace_dir / rel
            if file_path.is_file():
                size = file_path.stat().st_size
                art = record_artifact(session_id, file_path.name, rel, size)
                artifacts_meta.append(art)

        # 6. Save assistant message with tool details and files
        saved_msg = add_message(
            session_id=session_id,
            role="assistant",
            content=final_text,
            tool_calls=[{"name": r.get("tool"), "detail": r} for r in collected_tool_runs] if collected_tool_runs else None,
            files_generated=changed_files if changed_files else None,
        )

        return {
            "message": saved_msg,
            "tool_runs": collected_tool_runs,
            "files_generated": artifacts_meta,
            "workspace": str(sandbox.workspace_dir),
        }
