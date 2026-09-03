"""SQLite-backed session persistence.

Why: in-memory sessions die on restart and block horizontal scaling.
This store keeps conversation history in a single-file SQLite database
(stdlib only, zero extra dependencies), enabling:

* session survival across server restarts
* conversation history inspection / audit
* easy swap to Postgres/Redis later (same tiny interface)
"""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from pathlib import Path

from nutrimentor.config import PROJECT_ROOT

DEFAULT_DB = PROJECT_ROOT / "data" / "sessions.db"
SESSION_TTL_SECONDS = 7200  # 2h


class SessionStore:
    """Thread-safe SQLite session store with the same surface as the
    previous in-memory dict-of-Session, so engines can swap freely."""

    def __init__(self, db_path: Path | None = None, max_turns: int = 6) -> None:
        self.db_path = Path(db_path or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_turns = max_turns
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    persona TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id)"
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    def ensure_session(self, session_id: str | None, persona: str) -> str:
        sid = session_id or uuid.uuid4().hex[:12]
        self._cleanup_if_needed()
        return sid

    def append_turn(self, session_id: str, persona: str, question: str, answer: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO turns (session_id, persona, question, answer, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, persona, question[:2000], answer[:8000], time.time()),
            )
            self._conn.commit()

    def history_text(self, session_id: str, max_turns: int | None = None) -> str:
        """Render recent turns as prompt-ready history text."""
        n = max_turns or self.max_turns
        with self._lock:
            rows = self._conn.execute(
                "SELECT question, answer FROM turns WHERE session_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (session_id, n),
            ).fetchall()
        rows.reverse()
        lines = [f"问：{q}\n答：{a[:200]}…" if len(a) > 200 else f"问：{q}\n答：{a}"
                 for q, a in rows]
        return "\n\n".join(lines)

    def turn_count(self, session_id: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM turns WHERE session_id = ?", (session_id,)
            ).fetchone()
        return row[0]

    def _cleanup_if_needed(self) -> None:
        """Delete turns older than the session TTL (cheap, indexed)."""
        cutoff = time.time() - SESSION_TTL_SECONDS
        with self._lock:
            self._conn.execute("DELETE FROM turns WHERE created_at < ?", (cutoff,))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


# Module-level shared store (one connection per process)
_store: SessionStore | None = None


def get_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store
