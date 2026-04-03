from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator


@dataclass(slots=True)
class RequestRecord:
    user_id: int
    full_name: str
    username: str | None
    request_type: str
    details: str
    created_at: str


class Storage:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY,
                    title TEXT,
                    chat_type TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    full_name TEXT NOT NULL,
                    username TEXT,
                    request_type TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def upsert_chat(self, chat_id: int, title: str | None, chat_type: str) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chats(chat_id, title, chat_type, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    title=excluded.title,
                    chat_type=excluded.chat_type
                """,
                (chat_id, title, chat_type, now),
            )

    def list_chats(self) -> list[int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT chat_id FROM chats").fetchall()
        return [int(row["chat_id"]) for row in rows]

    def add_chat_message(self, chat_id: int, role: str, text: str) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_messages(chat_id, role, text, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (chat_id, role, text[:4000], now),
            )
            conn.execute(
                """
                DELETE FROM chat_messages
                WHERE chat_id = ?
                  AND id NOT IN (
                    SELECT id
                    FROM chat_messages
                    WHERE chat_id = ?
                    ORDER BY id DESC
                    LIMIT 30
                  )
                """,
                (chat_id, chat_id),
            )

    def get_recent_chat_messages(self, chat_id: int, limit: int = 8) -> list[dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, text
                FROM chat_messages
                WHERE chat_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()
        return [
            {"role": str(row["role"]), "text": str(row["text"])}
            for row in reversed(rows)
        ]

    def save_request(
        self,
        user_id: int,
        full_name: str,
        username: str | None,
        request_type: str,
        details: str,
    ) -> RequestRecord:
        now = datetime.now(tz=timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO requests(user_id, full_name, username, request_type, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, full_name, username, request_type, details, now),
            )

        return RequestRecord(
            user_id=user_id,
            full_name=full_name,
            username=username,
            request_type=request_type,
            details=details,
            created_at=now,
        )
