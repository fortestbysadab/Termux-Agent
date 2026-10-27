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
   - **Connectors Modal**: Beautiful UI matching standard connector hubs (GitHub, Notion, Linear, Google Drive, Docs, Sheets, Slides, Calendar, Gmail, Dropbox, Vercel, Supabase), each with its **real brand mark** from `simple-icons` (bundled, offline, no CDN).
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

5. **Real-time Live Command Streaming & Structured Error Cards**:
   - Live Server-Sent Events (SSE) stream the exact `$ BASH` command currently running on screen in real-time.
   - Expandable tool execution cards showing command status, exit codes, and stdout/stderr output.
   - Beautiful, structured Error Cards displaying actionable remedies directly in the UI instead of unparsed raw error dumps.

6. **Android Bionic Linker & Gemini Thinking Model Hardening**:
   - Bionic CFI-safe execution sandbox (omits virtual address caps that trigger `linker_cfi.cpp:158` aborts on Android).
   - Full support for Google Gemini 2.5/3 thinking models with automatic thought signature preservation and parameter schema sanitization.

7. **Zero External Runtime Dependencies**:
   - The server, database layer, MCP client and sandbox are pure Python standard library (`sqlite3`, `http.server`, `subprocess`, `urllib`).
   - The React console ships **pre-built** in `web/static/`, so `python3 main.py` is still the only command you need. Node is a build-time tool for developers only.
   - Automated CI testing via GitHub Actions across Python 3.10, 3.11, and 3.12.

8. **File Uploads (attachments)**:
   - Attach files from the composer (paperclip, drag-and-drop anywhere in the thread, or paste from the clipboard).
   - Everything is written to `uploads/` **inside that session's workspace**, size-checked (`AGENT_MAX_UPLOAD_MB`, 25 MB default), name-sanitised and de-duplicated (`report (2).pdf`), with an extension allowlist.
   - The agent is told exactly which files arrived, so "clean this CSV" or "turn this into a deck" works on the first try. Uploaded files are listed separately from agent output in the Workspace panel and are never modified by the agent.

9. **Vision-first files — no needless Python**:
   - When the planner model can see (Gemini 2.5, GPT-4o/4.1/5, Claude, Grok, Qwen-VL…), attached images are sent **into the turn as image content**, base64 and all — the model looks at the screenshot itself instead of running a script to describe it. `vision.build_content()` keeps PDFs, spreadsheets, archives and media on the tool path, where they belong.
   - Capability is detected from the model name (`AGENT_VISION=on|off|auto`), so a text-only model transparently falls back to shell inspection and is told to say so.
   - The system prompt states which mode is active, and only then does the "reach for Python" instinct kick in — for pixels that need measuring, OCR at scale, or formats no model reads natively.

10. **Skills — reusable procedures that compose, route and self-author**:
   - A skill is a directory of markdown: `skills/<name>/SKILL.md` with `name`, `title`, `description`, `when_to_use`, `uses[]`, `tools[]`, `icon` frontmatter. No code, no install step.
   - **Progressive disclosure**: only `name: description — when_to_use` goes into the system prompt; the full procedure is loaded by the `use_skill` tool when the model actually needs it.
   - **Skills calling skills**: a skill declares `uses: [a, b, c]` and `use_skill` loads it *plus* its dependencies in one call, each body headed with why it was pulled in. `report-bundle` composes `data-wrangler` + `svg-chart` + `xlsx-report` + `pdf-report` and emits a PDF, an XLSX, an SVG and a cleaned CSV, zipped.
   - **Router — skills load without being asked.** `SkillRouter` scores enabled skills against the request *and* the attached file types using each skill's `triggers` and `files` frontmatter. Say "read this PDF", attach a `.csv`, or ask to "chart the scores" and the matching skill (plus its dependencies) is already in the prompt before the model answers — no tool call, no wasted turn. Any prompt that matches nothing is untouched, so chit-chat costs nothing. The Skills screen has a live router tester (`GET /api/skills/router`) so the rules are inspectable instead of magic.
   - **Anyone can write a skill**: the *New skill* button (triggers, file types, dependencies, instructions), a `SKILL.md` dropped into `skills/`, or plain English in chat — ask for "save that as a skill" and the agent writes it with the `create_skill` tool. User and agent skills are badged *yours* / *by the agent* and can be edited or deleted from the UI; the six bundled skills can only be disabled.
   - Six skills ship in the box: `data-wrangler`, `svg-chart`, `xlsx-report`, `pdf-report`, `workspace-audit`, `report-bundle`. Enable/disable any of them from the Skills screen — the catalogue and the tool list update on the next turn, and run counters are kept in SQLite.

11. **Console built on [Libraries.dev](https://libraries.dev)**:
   - **Border Beam** (`border-beam`) — a single, subtle animated glow wrapped around **the chat composer only**, calm at rest, brighter and faster while the agent works.
   - **Thinking Orbs** (`thinking-orbs`) — every spinner replaced by an orb whose state is driven by the real SSE activity: `searching` (reasoning), `working` (running a command), `connecting` (calling a tool), `solving` (reading results), with crossfades between phases.
   - **Bot Avatars** (`bot-avatars`) — the planner, the shell and the MCP bridge each get their own animated identity (plush / plastic bodies, distinct colours) that switches as control passes between them. Connectors are shown as their own real brand logos, not as bots.
   - Full dark/light design system, `100dvh` mobile layout, off-canvas drawers, keyboard shortcuts, reduced-motion support and a render error boundary.

---

## 🚀 Quick Start on Termux

```bash
# 1. Update Termux and install Python + proot (no Node needed — the console is pre-built)
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
├── config.py                # Environment & paths (uploads dir, skill dir, limits)
├── db.py                    # SQLite database (sessions, history, connectors, artifacts, skill state)
├── skills.py                # SKILL.md discovery, dependency loading, router, authoring
├── uploads.py               # Multipart parsing, filename sanitising, uploads/ storage
├── vision.py                # model-capability detection + inline image content parts
├── skills/
│   ├── data-wrangler/SKILL.md
│   ├── svg-chart/SKILL.md
│   ├── xlsx-report/SKILL.md
│   ├── pdf-report/SKILL.md
│   ├── workspace-audit/SKILL.md
│   └── report-bundle/SKILL.md   # uses: the four above
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
    └── static/              # BUILD OUTPUT — committed so Python needs no Node
        ├── index.html       # Console shell
        ├── app.css          # Compiled design system
        └── app.js           # Compiled React console (React + Libraries.dev)

frontend/                    # Source for the console (build-time only)
├── build.mjs                # esbuild → web/static
├── index.html
└── src/                     # React components, styles, activity mapping
```

### Working on the console

```bash
cd frontend
npm install          # once
npm run build        # or: npm run watch
```

See [`frontend/README.md`](frontend/README.md) for the component sources, the
Border-Beam-is-composer-only rule, and the SSE-event → orb/avatar state map.
