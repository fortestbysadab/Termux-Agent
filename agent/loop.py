"""ReAct Agent Execution Loop with Tool Calling, Terminal Sandbox, and Workspace Diffing."""

import json
import logging
from pathlib import Path
from collections.abc import Callable
from typing import Any, Optional
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

    def run_turn(
        self,
        session_id: str,
        user_text: str,
        callback: Optional[Callable[[str, dict], None]] = None
    ) -> dict[str, Any]:
        """Execute one complete conversational agent turn with optional real-time event callbacks."""
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
                if m.get("files_generated"):
                    content = content + f"\n(Files available in workspace: {', '.join(m['files_generated'])})"
                messages.append({"role": "assistant", "content": content})

        # Append new user message
        messages.append({"role": "user", "content": user_text})
        add_message(session_id, "user", user_text)

        # Auto-update session title on first turn
        if len(history) == 0:
            clean_title = " ".join(user_text.split()[:5])[:36]
            update_session_title(session_id, clean_title or "New chat")

        # 4. Multi-turn Tool Calling Loop
        max_turns = 8
        collected_tool_runs = []
        final_text = ""
        error_info = None

        for turn in range(max_turns):
            if callback:
                callback("status", {"message": f"Planning turn {turn + 1}..."})

            response = self.planner.complete(messages, tools=all_tools)

            if response.get("error"):
                error_info = response["error"]
                if callback:
                    callback("error", error_info)
                final_text = f"⚠️ **{error_info['title']}**\n\n{error_info['message']}"
                if error_info.get("remedy"):
                    final_text += f"\n\n*Fix:* {error_info['remedy']}"
                break

            content = response.get("content")
            tool_calls = response.get("tool_calls", [])

            if not tool_calls:
                final_text = content or "Task completed."
                break

            # Format assistant message with tool calls
            assistant_msg = {"role": "assistant"}
            if content:
                assistant_msg["content"] = content
            formatted_tc = []
            for tc in tool_calls:
                call_dict = {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])},
                }
                if tc.get("extra_content"):
                    call_dict["extra_content"] = tc["extra_content"]
                formatted_tc.append(call_dict)
            assistant_msg["tool_calls"] = formatted_tc
            messages.append(assistant_msg)

            for tc in tool_calls:
                t_name = tc["name"]
                t_args = tc["arguments"]

                if t_name == "run_terminal_command":
                    cmd = t_args.get("command", "")
                    
                    # Notify UI of EXACT command starting
                    if callback:
                        callback("command_start", {"command": cmd, "tool": "terminal"})

                    exec_result = sandbox.run_command(cmd)
                    tool_content = f"STDOUT:\n{exec_result['stdout']}\nSTDERR:\n{exec_result['stderr']}\nExit Code: {exec_result['exit_code']}"
                    
                    cmd_info = {
                        "tool": "terminal",
                        "command": cmd,
                        "stdout": exec_result["stdout"],
                        "stderr": exec_result["stderr"],
                        "exit_code": exec_result["exit_code"],
                        "duration_ms": exec_result["duration_ms"],
                        "ok": exec_result["ok"],
                    }
                    collected_tool_runs.append(cmd_info)

                    # Notify UI of command completion
                    if callback:
                        callback("command_done", cmd_info)
                else:
                    # Connector or MCP tool
                    if callback:
                        callback("connector_start", {"tool": t_name, "arguments": t_args})
                    
                    res = self.connectors.execute_tool(t_name, t_args, routing)
                    tool_content = json.dumps(res) if isinstance(res, (dict, list)) else str(res)
                    
                    conn_info = {
                        "tool": t_name,
                        "arguments": t_args,
                        "result": res,
                        "ok": not ("error" in res if isinstance(res, dict) else False),
                    }
                    collected_tool_runs.append(conn_info)

                    if callback:
                        callback("connector_done", conn_info)

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

        outcome = {
            "message": saved_msg,
            "tool_runs": collected_tool_runs,
            "files_generated": artifacts_meta,
            "workspace": str(sandbox.workspace_dir),
            "error": error_info,
        }

        if callback:
            callback("done", outcome)

        return outcome
