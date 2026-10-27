"""SQLite database persistence for sessions, chat history, connectors, and artifacts."""

import json
import os
import shutil
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Optional
from config import DB_PATH, WORKSPACES_DIR

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tool_calls TEXT,
            tool_results TEXT,
            files_generated TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS connectors (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            description TEXT,
            config TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            rel_path TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            created_at REAL NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS skills (
            name TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1,
            runs INTEGER NOT NULL DEFAULT 0,
            last_used REAL
        );

        -- Round-trip state: the agent paused to ask the user something and the
        -- client will re-issue the request with the answers (MCP "input
        -- required" style). One row per pending question set.
        CREATE TABLE IF NOT EXISTS pending_inputs (
            token TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            user_text TEXT NOT NULL,
            questions TEXT NOT NULL,
            created_at REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_artifacts_session ON artifacts(session_id, created_at);
        """)

# --- Sessions ---

def list_sessions() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.title, s.created_at, s.updated_at,
                   COUNT(m.id) as message_count
            FROM sessions s
            LEFT JOIN messages m ON s.id = m.session_id
            GROUP BY s.id
            ORDER BY s.updated_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]

def create_session(title: str = "New Chat") -> dict[str, Any]:
    session_id = uuid.uuid4().hex[:12]
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (session_id, title, now, now),
        )
    # Ensure session workspace directory exists
    (WORKSPACES_DIR / session_id).mkdir(parents=True, exist_ok=True)
    return {"id": session_id, "title": title, "created_at": now, "updated_at": now, "message_count": 0}

def get_session(session_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(row) if row else None

def update_session_title(session_id: str, title: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, time.time(), session_id),
        )

def touch_session(session_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (time.time(), session_id),
        )

def delete_session(session_id: str) -> bool:
    with get_connection() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM artifacts WHERE session_id = ?", (session_id,))
        cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        deleted = cursor.rowcount > 0

    # Clean up workspace directory
    session_ws = WORKSPACES_DIR / session_id
    if session_ws.is_dir():
        shutil.rmtree(session_ws, ignore_errors=True)
    return deleted

def clear_all_sessions() -> int:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM sessions")
        count = cursor.rowcount

    # Clean up all workspace directories
    if WORKSPACES_DIR.is_dir():
        for item in WORKSPACES_DIR.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
    return count

# --- Messages ---

def add_message(
    session_id: str,
    role: str,
    content: str,
    tool_calls: Optional[list[dict]] = None,
    tool_results: Optional[list[dict]] = None,
    files_generated: Optional[list[str]] = None,
) -> dict[str, Any]:
    msg_id = uuid.uuid4().hex[:12]
    now = time.time()
    tc_json = json.dumps(tool_calls) if tool_calls else None
    tr_json = json.dumps(tool_results) if tool_results else None
    fg_json = json.dumps(files_generated) if files_generated else None

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO messages (id, session_id, role, content, tool_calls, tool_results, files_generated, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (msg_id, session_id, role, content, tc_json, tr_json, fg_json, now),
        )
        conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))

    return {
        "id": msg_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "files_generated": files_generated,
        "created_at": now,
    }

def get_messages(session_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        messages = []
        for r in rows:
            d = dict(r)
            d["tool_calls"] = json.loads(d["tool_calls"]) if d["tool_calls"] else None
            d["tool_results"] = json.loads(d["tool_results"]) if d["tool_results"] else None
            d["files_generated"] = json.loads(d["files_generated"]) if d["files_generated"] else None
            messages.append(d)
        return messages

# --- Connectors ---

def list_connectors() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM connectors ORDER BY created_at ASC").fetchall()
        connectors = []
        for r in rows:
            d = dict(r)
            d["config"] = json.loads(d["config"]) if d["config"] else {}
            d["enabled"] = bool(d["enabled"])
            connectors.append(d)
        return connectors

def get_connector(connector_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM connectors WHERE id = ?", (connector_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["config"] = json.loads(d["config"]) if d["config"] else {}
        d["enabled"] = bool(d["enabled"])
        return d

def upsert_connector(
    connector_id: str,
    name: str,
    kind: str,
    description: str,
    config: dict[str, Any],
    enabled: int = 0,
) -> None:
    now = time.time()
    config_json = json.dumps(config)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO connectors (id, name, kind, description, config, enabled, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                kind = excluded.kind,
                description = excluded.description,
                config = excluded.config,
                enabled = excluded.enabled
            """,
            (connector_id, name, kind, description, config_json, enabled, now),
        )

def toggle_connector(connector_id: str, enabled: Optional[bool] = None) -> bool:
    with get_connection() as conn:
        current = conn.execute("SELECT enabled FROM connectors WHERE id = ?", (connector_id,)).fetchone()
        if not current:
            return False
        new_val = (1 - current["enabled"]) if enabled is None else (1 if enabled else 0)
        conn.execute("UPDATE connectors SET enabled = ? WHERE id = ?", (new_val, connector_id))
        return bool(new_val)

def delete_connector(connector_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM connectors WHERE id = ?", (connector_id,))
        return cursor.rowcount > 0

# --- Artifacts ---

def record_artifact(session_id: str, filename: str, rel_path: str, size_bytes: int) -> dict[str, Any]:
    art_id = uuid.uuid4().hex[:12]
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO artifacts (id, session_id, filename, rel_path, size_bytes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (art_id, session_id, filename, rel_path, size_bytes, now),
        )
    return {
        "id": art_id,
        "session_id": session_id,
        "filename": filename,
        "rel_path": rel_path,
        "size_bytes": size_bytes,
        "created_at": now,
    }

def list_artifacts(session_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM artifacts WHERE session_id = ? ORDER BY created_at DESC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# --- Skills ---

def get_skill_states() -> dict[str, dict[str, Any]]:
    """{name: {enabled, runs, last_used}} for every skill we have a row for."""
    with get_connection() as conn:
        rows = conn.execute("SELECT name, enabled, runs, last_used FROM skills").fetchall()
        return {
            r["name"]: {
                "enabled": bool(r["enabled"]),
                "runs": r["runs"],
                "last_used": r["last_used"],
            }
            for r in rows
        }

def set_skill_enabled(name: str, enabled: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO skills (name, enabled) VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET enabled = excluded.enabled
            """,
            (name, 1 if enabled else 0),
        )

def record_skill_run(name: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO skills (name, enabled, runs, last_used) VALUES (?, 1, 1, ?)
            ON CONFLICT(name) DO UPDATE SET
                runs = skills.runs + 1,
                last_used = excluded.last_used
            """,
            (name, time.time()),
        )


# --- Pending questions (elicitation round-trips) ---

def save_pending_input(token: str, session_id: str, user_text: str, questions: list) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO pending_inputs (token, session_id, user_text, questions, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (token, session_id, user_text, json.dumps(questions, ensure_ascii=False), time.time()),
        )


def get_pending_input(token: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT token, session_id, user_text, questions, created_at FROM pending_inputs WHERE token = ?",
            (token,),
        ).fetchone()
    if not row:
        return None
    return {
        "token": row["token"],
        "session_id": row["session_id"],
        "user_text": row["user_text"],
        "questions": json.loads(row["questions"]),
        "created_at": row["created_at"],
    }


def delete_pending_input(token: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM pending_inputs WHERE token = ?", (token,))


def prune_pending_inputs(max_age: float = 3600.0) -> int:
    cutoff = time.time() - max_age
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM pending_inputs WHERE created_at < ?", (cutoff,))
        return cur.rowcount
