from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from typing import Iterable, Optional
from uuid import uuid4

from app.models.session import (
    PersonaTurn,
    SessionConfig,
    SessionPersona,
    SessionRecord,
    SessionTurn,
)


class TeamSessionStore:
    """SQLite-backed storage for team sessions and turn history."""

    def __init__(self, db_path: str = "data/skiller_sessions.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS team_sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    seed_task TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    config_json TEXT NOT NULL,
                    personas_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS team_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    turn_id INTEGER NOT NULL,
                    task TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    persona_turns_json TEXT NOT NULL,
                    session_summary TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, turn_id),
                    FOREIGN KEY(session_id) REFERENCES team_sessions(session_id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_team_turns_session_id ON team_turns(session_id, turn_id)"
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _generate_session_id() -> str:
        return f"session-{uuid4().hex[:12]}"

    @staticmethod
    def _session_row_to_record(row: sqlite3.Row, turns: list[SessionTurn]) -> SessionRecord:
        config = SessionConfig.model_validate(json.loads(row["config_json"]))
        personas = [SessionPersona.model_validate(item) for item in json.loads(row["personas_json"])]
        return SessionRecord(
            session_id=row["session_id"],
            title=row["title"],
            seed_task=row["seed_task"],
            summary=row["summary"],
            config=config,
            personas=personas,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            turns=turns,
        )

    @staticmethod
    def _turn_row_to_record(row: sqlite3.Row) -> SessionTurn:
        persona_turns = [PersonaTurn.model_validate(item) for item in json.loads(row["persona_turns_json"])]
        return SessionTurn(
            turn_id=row["turn_id"],
            task=row["task"],
            answer=row["answer"],
            created_at=datetime.fromisoformat(row["created_at"]),
            persona_turns=persona_turns,
            session_summary=row["session_summary"],
        )

    def create_session(
        self,
        *,
        seed_task: str,
        config: SessionConfig,
        personas: Iterable[SessionPersona],
        session_id: Optional[str] = None,
        summary: str = "",
        title: Optional[str] = None,
    ) -> SessionRecord:
        session_id = session_id or self._generate_session_id()
        now = self._now()
        persona_list = list(personas)
        session_title = title or seed_task[:80].strip() or "Skiller Session"

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO team_sessions (
                    session_id, title, seed_task, summary, config_json, personas_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    session_title,
                    seed_task,
                    summary,
                    config.model_dump_json(),
                    json.dumps([persona.model_dump() for persona in persona_list], ensure_ascii=False),
                    now,
                    now,
                ),
            )

        return SessionRecord(
            session_id=session_id,
            title=session_title,
            seed_task=seed_task,
            summary=summary,
            config=config,
            personas=persona_list,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
            turns=[],
        )

    def session_exists(self, session_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM team_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return row is not None

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM team_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            turns = self.list_turns(session_id, connection=conn)
        return self._session_row_to_record(row, turns)

    def list_turns(
        self,
        session_id: str,
        *,
        limit: Optional[int] = None,
        connection: Optional[sqlite3.Connection] = None,
    ) -> list[SessionTurn]:
        sql = "SELECT * FROM team_turns WHERE session_id = ? ORDER BY turn_id ASC"
        params: list[object] = [session_id]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        close_connection = False
        conn = connection
        if conn is None:
            conn = self._connect()
            close_connection = True

        try:
            rows = conn.execute(sql, params).fetchall()
            return [self._turn_row_to_record(row) for row in rows]
        finally:
            if close_connection:
                conn.close()

    def get_recent_turns(self, session_id: str, limit: int = 5) -> list[SessionTurn]:
        turns = self.list_turns(session_id)
        return turns[-limit:]

    def append_turn(
        self,
        *,
        session_id: str,
        task: str,
        answer: str,
        persona_turns: Iterable[PersonaTurn],
        session_summary: str,
    ) -> SessionTurn:
        persona_turn_list = list(persona_turns)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(turn_id), 0) + 1 AS next_turn_id FROM team_turns WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            turn_id = int(row["next_turn_id"]) if row else 1
            now = self._now()
            conn.execute(
                """
                INSERT INTO team_turns (
                    session_id, turn_id, task, answer, persona_turns_json, session_summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    turn_id,
                    task,
                    answer,
                    json.dumps([item.model_dump() for item in persona_turn_list], ensure_ascii=False),
                    session_summary,
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE team_sessions
                SET summary = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (session_summary, now, session_id),
            )
        return SessionTurn(
            turn_id=turn_id,
            task=task,
            answer=answer,
            created_at=datetime.fromisoformat(now),
            persona_turns=persona_turn_list,
            session_summary=session_summary,
        )

    def update_session_summary(self, session_id: str, summary: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE team_sessions
                SET summary = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (summary, self._now(), session_id),
            )
