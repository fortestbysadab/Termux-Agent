# Termux Agent ⚡

An autonomous AI agent with **Full Terminal Access**, **Connectors & Custom MCP (Model Context Protocol)**, and **Per-Session Isolated Workspaces**, built specifically to run natively inside **Termux on an unrooted Android phone** (as well as any Linux/macOS machine).

---

## 🌟 Key Features

1. **Full Terminal Execution**:
   - The agent can execute any Linux/Bash terminal command (`run_terminal_command`) to install packages, run scripts (Python, JS, C, Bash), compile code, and process data.
   - **Per-Session Isolation**: Every session has its own dedicated workspace directory (`~/agent_workspaces/<session_id>/`).
   - **Proot Containment**: When running inside Termux, `proot` jails execution to the session workspace, hiding `$HOME`, `/sdcard`, and `.env` so secrets are never leaked.
   - Resource limits (CPU caps, memory caps, timeout watchdog).

2. **Connectors & Custom MCP (Model Context Protocol)**:
   - **Connectors Modal**: Beautiful UI matching standard connector hubs (GitHub, Notion, Linear, Google Drive, Docs, Sheets, Slides, Calendar, Gmail, Dropbox, Vercel, Supabase).
   - **Custom MCP Connector**: Connect any standard MCP server via local **stdio command** (e.g. `npx -y @modelcontextprotocol/server-postgres`) or **remote HTTP/SSE endpoint**.
   - Dynamic tool discovery: Tools from enabled connectors are automatically injected into the agent's active tool list.

3. **Workspace vs. Chat Decision & Artifacts**:
   - Filesystem tracker snapshots the workspace before and after each turn.
   - **If files are created/modified**: An **Artifact Card** is displayed in chat with file size, download link, and instant in-browser preview, and saved to the session's **Workspace Files** drawer.
   - **If no files are created**: Clear conversational response directly in chat with collapsible terminal command executions.

4. **Persistent Chat History & Session Management**:
   - Full chat history is automatically persisted in SQLite (`agent.db`).
   - Switch between conversations seamlessly from the sidebar.
   - Delete individual conversations (and their associated workspace files) or clear all history at any time.

5. **Zero External Dependencies**:
   - Built entirely on Python standard library (`sqlite3`, `http.server`, `subprocess`, `urllib`).
   - Fast, lightweight, and requires no heavy compilation on Termux.

---

## 🚀 Quick Start on Termux

```bash
# 1. Update Termux and install Python + proot
pkg update && pkg install -y python git proot

# 2. Clone the repository (or copy this folder to Termux)
cd termux-agent

# 3. Configure your LLM API Key (Gemini, OpenAI, Groq, Ollama)
cp .env.example .env
nano .env

# 4. Start the agent
python main.py
```

Open `http://localhost:8080` in your Android browser (Chrome, Firefox, Kiwi).

---

## 📂 Project Structure

```text
termux-agent/
├── main.py                  # Entry point
├── config.py                # Environment & paths
├── db.py                    # SQLite database (sessions, history, connectors, artifacts)
├── sandbox/
│   ├── runner.py            # Per-session proot & subprocess terminal runner
│   └── tracker.py           # Workspace snapshot & change detection
├── connectors/
│   ├── builtin.py           # Catalog of standard connectors (GitHub, Linear, Notion, etc.)
│   ├── mcp_client.py        # Model Context Protocol stdio & SSE client
│   └── manager.py           # Connector registry & tool routing
├── agent/
│   ├── planner.py           # OpenAI/Gemini compatible LLM planner
│   └── loop.py              # ReAct loop, tool execution & file detection
└── web/
    ├── server.py            # HTTP server (zero pip dependencies)
    └── static/
        ├── index.html       # Single-page web console & Connectors Modal
        ├── styles.css       # Clean, modern responsive design
        └── app.js           # Client-side reactivity & API integration
```
