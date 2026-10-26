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
- If the user asks for a file (document, script, CSV, HTML, analysis, code), ALWAYS write/create the file in the workspace using terminal commands.
- CRITICAL ANDROID / TERMUX ENVIRONMENT CONSTRAINTS:
  1. NO HEAVY PIP COMPILATION: NEVER attempt to compile or install heavy C/C++ libraries from source via `pip install` (e.g. `matplotlib`, `scipy`, `pandas`, `scikit-learn`, `numpy`, `torch`, `cv2`). They take 20+ minutes and time out (Exit -1) on Android ARM64 phones.
  2. FOR CHARTS, PLOTS, GRAPHS & VISUALIZATIONS:
     ALWAYS generate clean, professional, high-resolution SVG files (`.svg`) or HTML5 Canvas directly in Python using standard libraries!
     Python can generate stunning, colorful, high-resolution vector bar charts, line graphs, and pie charts in 0.01 seconds with ZERO pip dependencies.
     When the user asks for a chart, graph, or picture demo (e.g. "Create chart bars pic demo about ai growth"):
     Write and save a professional `.svg` file (e.g. `ai_growth_chart.svg`). It displays instantly as an image in all browsers and device previewers.
  3. TIMEOUT RESILIENCE: If any command times out (Exit -1) or fails, DO NOT retry compiling packages. Immediately switch to pure Python or SVG.
- STRICT FILE DISCIPLINE:
  1. Output the final requested deliverable file directly in the workspace root (e.g. `7_day_study_habit_plan.xlsx`, `neuroscience_overview.pdf`, `ai_growth_chart.svg`).
  2. NEVER create scratch test files (such as `test.xlsx`, `test.pdf`, `dummy.txt`) in the workspace root. If you need temporary files, write them into `.tmp/` or delete them before completing the turn (`rm -f test.*`).
  3. Clean up helper generator scripts (e.g. `generate_sheets.py`, `generate_pdf.py`). Execute code via `python3 -c "..."` or remove the script after running (`rm -f generate_*.py`).
  4. Only the exact asking deliverable files should remain in the workspace.
- If the task is purely conversational or an inquiry without file requests, answer directly in chat.
- After running terminal commands, explain the results clearly. Be concise, direct, and helpful.
"""

DELIVERABLE_EXTENSIONS = frozenset({
    ".pdf", ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp",
    ".csv", ".tsv", ".html", ".htm",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg",
    ".mp3", ".wav", ".m4a", ".mp4", ".webm", ".mov",
    ".zip", ".tar", ".gz", ".7z",
    ".json", ".xml", ".yaml", ".yml", ".txt", ".md",
})

SCRIPT_EXTENSIONS = frozenset({
    ".py", ".sh", ".bash", ".zsh", ".js", ".ts", ".rb", ".php", ".pl",
})

def is_scratch_file(rel_path: str) -> bool:
    """Identify temporary scratch, helper generator scripts, or test files."""
    p = Path(rel_path)
    name = p.name.lower()
    ext = p.suffix.lower()
    if ext in (".tmp", ".bak", ".swp", ".pyc"):
        return True
    if any(name.startswith(pfx) for pfx in ("test.", "test_", "test1.", "test2.", "temp.", "temp_", "tmp.", "scratch.", "dummy.", "dummy_")):
        return True
    if any(name.startswith(pfx) for pfx in ("gen_", "generate_", "create_", "make_", "build_", "run_", "script.")) and ext in (".py", ".sh", ".bash", ".js"):
        return True
    return False

def is_primary_deliverable(rel_path: str) -> bool:
    """Identify if a file is a finished user deliverable (document, media, spreadsheet, data)."""
    p = Path(rel_path)
    if is_scratch_file(rel_path):
        return False
    return p.suffix.lower() in DELIVERABLE_EXTENSIONS

def filter_chat_artifacts(changed_files: list[str], user_text: str = "") -> list[str]:
    """Filter intermediate build/generator scripts out of chat deliverable cards when a deliverable exists.
    All files remain saved and accessible in the Workspace Files view ('all files means all files')."""
    if not changed_files or len(changed_files) <= 1:
        return changed_files

    user_lower = (user_text or "").lower()
    user_wants_script = any(
        kw in user_lower
        for kw in ("python", "py file", ".py", "script", "code", "bash", "shell", ".sh", "write a program")
    )

    deliverables = []
    scripts = []

    for f in changed_files:
        if is_primary_deliverable(f):
            deliverables.append(f)
        elif is_scratch_file(f):
            scripts.append(f)
        else:
            deliverables.append(f)

    # If there are primary deliverables (e.g. PDF, image, document, dataset) and user didn't ask for a script,
    # show only the deliverables in the chat card.
    if deliverables and not user_wants_script:
        return deliverables

    return changed_files

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

        # Check if primary deliverables were generated
        primary_deliverables = [f for f in changed_files if is_primary_deliverable(f)]

        # If primary deliverables exist, automatically clean scratch and test files from the workspace
        # (e.g., delete test.xlsx, generate_*.py so only asking files remain saved in the workspace)
        if primary_deliverables:
            cleaned_changed = []
            for rel in changed_files:
                if is_scratch_file(rel):
                    f_to_del = sandbox.workspace_dir / rel
                    try:
                        if f_to_del.is_file():
                            f_to_del.unlink(missing_ok=True)
                    except Exception:
                        pass
                else:
                    cleaned_changed.append(rel)
            changed_files = cleaned_changed

        # Record generated artifacts in database (all files tracked for workspace files view)
        artifacts_meta = []
        for rel in changed_files:
            file_path = sandbox.workspace_dir / rel
            if file_path.is_file():
                size = file_path.stat().st_size
                art = record_artifact(session_id, file_path.name, rel, size)
                artifacts_meta.append(art)

        # Smart filter for chat message deliverable cards:
        # Don't show intermediate generator scripts (e.g. generate_pdf.py) when a primary deliverable (.pdf) was produced.
        chat_deliverables = filter_chat_artifacts(changed_files, user_text=user_text)

        # 6. Save assistant message with tool details and files
        saved_msg = add_message(
            session_id=session_id,
            role="assistant",
            content=final_text,
            tool_calls=[{"name": r.get("tool"), "detail": r} for r in collected_tool_runs] if collected_tool_runs else None,
            files_generated=chat_deliverables if chat_deliverables else None,
        )

        chat_artifacts_meta = [a for a in artifacts_meta if a["rel_path"] in chat_deliverables] if chat_deliverables else []

        outcome = {
            "message": saved_msg,
            "tool_runs": collected_tool_runs,
            "files_generated": chat_artifacts_meta,
            "workspace": str(sandbox.workspace_dir),
            "error": error_info,
        }

        if callback:
            callback("done", outcome)

        return outcome
