# Product Requirements Document (PRD): Termux Agent ⚡

**Document Version:** 2.0.0  
**Status:** Active / Production-Ready  
**Repository:** [https://github.com/fortestbysadab/Termux-Agent.git](https://github.com/fortestbysadab/Termux-Agent.git)  
**Target Environments:** Termux (Android unrooted), Linux, macOS, and Desktop Web Browsers  

---

## 1. Executive Summary & Vision

### 1.1 The Vision
**Termux Agent** is a standalone, private, autonomous AI Agent engineering platform designed to run natively on mobile devices via Termux on an unrooted Android smartphone, as well as on any Linux or macOS computer.

Instead of being a simple chatbot, Termux Agent is an **autonomous software engineer and computing engine** in your pocket. It possesses full terminal execution capabilities, per-session isolated directory sandboxes, Model Context Protocol (MCP) connectivity, live Server-Sent Events (SSE) command streaming, and an Arena-inspired responsive console.

### 1.2 Our Primary Goal
> **To turn any everyday Android smartphone into a private, self-contained AI workstation that can run shell commands, generate real deliverables (PDFs, Excel spreadsheets, SVG graphics, codebases), manage isolated workspaces, and interface with external cloud services — with zero mandatory third-party pip dependencies, zero cloud telemetry, and 100% responsiveness across phones, tablets, foldables, and desktops.**

---

## 2. Core Problem Statement

Traditional mobile AI assistants suffer from major limitations:
1. **Read-Only / Conversational Toys**: Standard mobile AI apps can only generate text or code snippets inside markdown blocks. Users are forced to manually copy-paste code, set up files, and execute them by hand.
2. **Lack of Local Execution**: They cannot run Linux commands, install packages, process CSVs, compile scripts, or test their own work.
3. **Resource & Compilation Traps on Android**: Android uses a Bionic libc dynamic linker and ARM64 architecture. When standard AI agents attempt to compile heavy C/C++ libraries (such as `matplotlib`, `scipy`, or `pandas`) via `pip install`, the compilation hangs for 30 minutes, crashes from out-of-memory errors, or triggers dynamic linker aborts (`linker_cfi.cpp:158 MapShadow CHECK failed`).
4. **Cluttered Deliverable Hygiene**: Naive agents often litter the workspace with temporary test files (`test.xlsx`, `temp.py`, `generate_pdf.py`), confusing the user about which file is the finished deliverable.
5. **Rigid, Non-Responsive UIs**: Many web consoles fail on mobile or tablet form factors — navigation headers scroll off-screen, command outputs overflow horizontally, and binary deliverables like Excel or PDF show raw garbled characters.

---

## 3. Product Principles & Pillars

### Pillar 1: Native Terminal Power with Sandboxed Isolation
* The agent has full access to `run_terminal_command` to execute bash commands, run Python/Node scripts, process data, and verify outputs.
* **Per-Session Isolation**: Every chat conversation is assigned a dedicated workspace directory:
  `~/.termux_agent_data/workspaces/<session_id>/`
  Session A cannot read, modify, or pollute Session B's files.
* **PRoot Containment**: When running inside Termux, PRoot jails execution to the workspace, hiding parent user keys, `/sdcard`, and system credentials.

### Pillar 2: Strict File Hygiene & Intent Precision
* **"All Files Means All Files"**: The dedicated **Workspace Box** lists every file created in the session with live sizes and one-click ZIP download.
* **Deliverable Cleanliness in Chat**: When the user requests a specific deliverable (e.g. an Excel habit plan or a PDF report), the agent automatically purges scratch generator scripts (e.g. `generate_sheets.py`) and test artifacts (e.g. `test.xlsx`).
* The chat response attaches **only the exact deliverable requested**, keeping the conversation focused and pristine.

### Pillar 3: Real-Time Transparency (Zero Blind Execution)
* Users must never wonder what the AI is doing in the background.
* Every command execution is streamed live via **Server-Sent Events (SSE)**.
* The UI displays an active **$ BASH <exact_command>** card in real time, followed by collapsible execution cards detailing duration, exit codes, stdout, and stderr.

### Pillar 4: Zero External Runtime Dependencies
* The entire server, SQLite database layer, MCP client, and terminal sandbox run on the **Python 3 standard library** (`sqlite3`, `http.server`, `subprocess`, `urllib`, `zipfile`, `xml.etree.ElementTree`).
* No mandatory `pip install` commands required to boot the platform. Works out of the box in a fresh Termux environment with just `pkg install python git`.

### Pillar 5: Universal Device Responsiveness
* Seamlessly adapts across **Mobile (< 640px)**, **Tablet & Foldables (641px – 1024px)**, and **Desktop (> 1024px)** using dynamic viewport height (`100dvh`), off-canvas drawers, backdrop scrims, and horizontal scroll isolation.

---

## 4. Architectural Overview

```text
+---------------------------------------------------------------------------------+
|                                 USER BROWSER                                    |
|   (Mobile Phone / Android Tablet / Foldable / Desktop Chrome, Firefox, Safari)  |
+---------------------------------------------------------------------------------+
                                       │
                      HTTP / SSE REST API (:8080)
                                       ▼
+---------------------------------------------------------------------------------+
|                             TERMUX AGENT SERVER                                 |
|                         (Python 3 Standard Library)                             |
+---------------------------------------------------------------------------------+
      │                       │                             │
      ▼                       ▼                             ▼
+──────────────+    +───────────────────+         +───────────────────+
|   DATABASE   |    |    AGENT LOOP     |         |    CONNECTORS     |
| (agent.db)   |    |   (ReAct Loop)    |         |    (MCP Hub)      |
|              |    |                   |         |                   |
| - Sessions   |    | - Planner (LLM)   |         | - GitHub, Google  |
| - Messages   |    | - Auto-Diff Snap  |         | - Notion, Linear  |
| - Artifacts  |    | - File Cleaner    |         | - Custom stdio    |
| - Connectors |    | - SSE Streamer    |         | - Custom SSE      |
+──────────────+    +───────────────────+         +───────────────────+
                              │
                              ▼
            +───────────────────────────────────+
            |      PER-SESSION SANDBOX          |
            |                                   |
            | - Isolated Working Dir            |
            |   (~/.termux_agent_data/workspaces)
            | - PRoot Containment               |
            | - C++ pip Interceptor (SVG Fast)  |
            | - Timeout Watchdog (60s)          |
            +───────────────────────────────────+
```

---

## 5. Detailed Feature Specifications

### 5.1 Per-Session Workspace Box Panel (Arena-Inspired)
* **Header Bar**:
  * Title: `Workspace`
  * One-Click **Download ZIP** (`GET /api/workspace/<session_id>/zip`): Packages the entire active workspace into a zip archive with zero external utilities.
  * Live Quota & File Counter: Displays current usage (e.g. `4.2 KB / 128.0 MB · 2 files`).
* **Processes Section**:
  * Displays active background services (e.g. `● Termux Agent Server :8080`) with live health indicators.
* **Session File List**:
  * Lists all files in the current session workspace with file type badges (`PDF`, `XLSX`, `CSV`, `SVG`, `PNG`, `PY`).
  * Direct inline action buttons: **View** and **Download**.

### 5.2 Rich Multi-Format Preview Modal
When the user clicks **View** on any workspace file, the system dynamically routes to dedicated preview engines:
* **Spreadsheets (`.xlsx`, `.csv`, `.tsv`)**:
  * Automatically parsed on the backend via standard library `zipfile` and `xml.etree.ElementTree` (with `openpyxl` fallback).
  * Renders a responsive, interactive HTML table with sticky headers, striped rows, and clean cell padding.
* **PDF Documents (`.pdf`)**:
  * Because mobile Android Chrome disables inline PDF rendering inside standard `<iframe>` tags, Termux Agent renders a **PDF Document Card** with document metadata, an **Open in PDF Viewer** button (which launches Android's native PDF reader / new tab), a **Download PDF** button, and an embedded viewer fallback.
* **Images & Vector Graphics (`.svg`, `.png`, `.jpg`, `.webp`)**:
  * Renders inline with zoomable, touch-friendly containers.
* **Code & Text (`.py`, `.sh`, `.json`, `.md`, `.txt`)**:
  * Renders in a scrollable, syntax-friendly monospace container.

### 5.3 Android / Termux Package Interceptor & SVG Engine
* **The Problem**: Agents frequently attempt to install `matplotlib`, `scipy`, or `pandas` on mobile ARM64 devices, causing endless timeouts.
* **The Interceptor (`sandbox/runner.py`)**:
  * Intercepts `pip install` on known heavy C++ packages and `apt-get` commands in **10 milliseconds**.
  * Outputs clear guidance: *"Compiling heavy C++ packages from source via pip times out on Android ARM64 devices. Generate clean high-resolution SVG (.svg) or HTML5 Canvas directly in Python using standard libraries."*
* **The Result**: The agent immediately pivots to pure Python vector SVG generation (0.01 seconds, zero dependencies, responsive across all screens).

### 5.4 UI Micro-Interactions (Powered by `libraries.dev`)

> **Implementation note (v2.1):** the console is now a React 18 app bundled at build time
> (`frontend/`) into `web/static/app.js`, so the Python server keeps its zero-runtime-dependency
> guarantee. **Border Beam wraps the chat composer and nothing else** — see
> `frontend/README.md` for the state map that drives the orbs and avatars.
* **Border Beam (`border-beam`)**:
  * An animated gradient beam riding around the border of active in-progress command executions and status cards.
  * Supported variants: `colorful` (purple -> pink -> cyan -> emerald), `ocean`, `sunset`, and `mono`.
* **Thinking Orb (`thinking-orbs`)**:
  * Replaces generic loading spinners with a multi-layered, fluid, glowing canvas sphere.
  * Dynamically transitions through states: `searching` (planning), `working` (executing bash), and `solving` (finalizing output).
* **Bot Avatars (`bot-avatars`)**:
  * Interactive 2D Canvas avatar rendered with lighting, bead eyes, and rounded form.
  * Eyes smoothly track touch and mouse movement across the screen.
  * Automatically hops and spins when running commands or clicked.

---

## 6. Target User Personas & Use Cases

| Persona | Primary Goal | How Termux Agent Empowers Them |
| :--- | :--- | :--- |
| **Mobile Developers & Sysadmins** | Run scripts, inspect git repos, and debug on the go. | Full terminal execution directly on their phone without carrying a laptop. |
| **Students & Researchers** | Generate study plans, analyze data, and build reports. | Create colorful Excel schedules and comprehensive PDF research papers natively on mobile. |
| **Privacy-Focused Builders** | Keep proprietary code and private files on-device. | Complete local execution; files never leave `~/.termux_agent_data/workspaces/`. |
| **Automation Power Users** | Connect external tools to their local terminal. | Seamlessly integrate GitHub, Notion, Linear, or custom MCP servers over stdio and SSE. |

---

## 7. Non-Functional & System Requirements

1. **Storage Footprint**: Total engine size < 5 MB.
2. **Execution Overhead**: Fast startup (< 0.2s to boot HTTP server).
3. **Android Bionic Linker Safety**: Must NOT restrict virtual address space (`RLIMIT_AS`), ensuring full compatibility with Android Control Flow Integrity (`linker_cfi.cpp`).
4. **Provider Compatibility**: Fully normalized for OpenAI-compatible endpoints, Groq, Ollama, and Google Gemini (including thinking models with `thought_signature` preservation).
5. **Persistence Guarantee**: SQLite running in WAL mode with Foreign Key cascades ensures zero database lockups or corrupted history on mobile process termination.

---

## 8. Future Roadmap

- [x] Per-session isolated terminal sandboxes with PRoot containment.
- [x] Built-in catalog of 12 cloud connectors + Custom MCP servers (stdio & SSE).
- [x] Real-time command streaming via Server-Sent Events (SSE).
- [x] Arena-style Workspace Box with live ZIP archive downloads.
- [x] Multi-format rich previewers (Excel tables, PDF cards, SVG images).
- [x] Strict deliverable file hygiene with automatic scratch/test purging.
- [x] Full mobile, tablet, and desktop responsive UI with `100dvh`.
- [x] Border Beam, Thinking Orb, and Bot Avatar canvas components.
- [ ] **v2.1**: In-browser Monaco / Ace code editor within the Workspace Box for live editing.
- [ ] **v2.2**: Native voice input and speech feedback using Android WebSpeech API.
- [ ] **v2.3**: One-click local LLM bridge with on-device `llama.cpp` / Ollama inside Termux.
