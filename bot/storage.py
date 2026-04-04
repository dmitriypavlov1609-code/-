from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone, date
from typing import Iterator, Any
import logging

logger = logging.getLogger(__name__)

# Optional PostgreSQL support
try:
    import psycopg2
    import psycopg2.pool
    import psycopg2.extras
    from psycopg2.extensions import register_adapter, AsIs
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logger.warning("psycopg2 not available - PostgreSQL support disabled")


@dataclass(slots=True)
class RequestRecord:
    user_id: int
    full_name: str
    username: str | None
    request_type: str
    details: str
    created_at: str


class Storage:
    """
    Unified storage layer supporting both SQLite and PostgreSQL.

    Uses PostgreSQL when:
    - postgres_url is provided
    - POSTGRES_AVAILABLE is True

    Falls back to SQLite otherwise.
    """

    def __init__(
        self,
        db_path: str = "bot_data.sqlite3",
        postgres_url: str = "",
        use_postgres: bool = False,
    ) -> None:
        self.db_path = db_path
        self.postgres_url = postgres_url
        self.use_postgres = use_postgres and POSTGRES_AVAILABLE and bool(postgres_url)

        if self.use_postgres:
            logger.info("Using PostgreSQL storage")
            self._init_postgres()
        else:
            logger.info("Using SQLite storage")
            self._init_sqlite()

    # ========================================================================
    # Connection Management
    # ========================================================================

    def _init_postgres(self) -> None:
        """Initialize PostgreSQL connection pool."""
        if not POSTGRES_AVAILABLE:
            raise RuntimeError("psycopg2 not available")

        try:
            # Create connection pool (min 1, max 10 connections)
            self.pg_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=self.postgres_url,
            )
            logger.info("PostgreSQL connection pool created")

            # Test connection and create tables if needed
            with self._pg_connect() as conn:
                # Basic table creation (full schema in postgres_schema.sql)
                self._create_postgres_tables(conn)

        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL: {e}")
            raise

    def _init_sqlite(self) -> None:
        """Initialize SQLite database."""
        with self._sqlite_connect() as conn:
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

    def _create_postgres_tables(self, conn) -> None:
        """Create basic PostgreSQL tables (minimal version)."""
        cur = conn.cursor()
        try:
            # Enable pgvector if available
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            except Exception:
                logger.warning("pgvector extension not available")

            # Core tables
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id BIGINT PRIMARY KEY,
                    title TEXT,
                    chat_type TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    language_code TEXT DEFAULT 'ru',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    chat_id BIGINT,
                    full_name TEXT NOT NULL,
                    username TEXT,
                    request_type TEXT NOT NULL,
                    details TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id BIGSERIAL PRIMARY KEY,
                    chat_id BIGINT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
                    text TEXT NOT NULL,
                    message_metadata JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)

            # Create indexes
            cur.execute("CREATE INDEX IF NOT EXISTS idx_requests_user_id ON requests(user_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_id ON chat_messages(chat_id, created_at DESC);")

            conn.commit()
        except Exception as e:
            logger.error(f"Error creating PostgreSQL tables: {e}")
            conn.rollback()
            raise
        finally:
            cur.close()

    @contextmanager
    def _sqlite_connect(self) -> Iterator[sqlite3.Connection]:
        """SQLite connection context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @contextmanager
    def _pg_connect(self) -> Iterator[Any]:
        """PostgreSQL connection context manager."""
        conn = self.pg_pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pg_pool.putconn(conn)

    # ========================================================================
    # Core Methods (backwards compatible)
    # ========================================================================

    def upsert_chat(self, chat_id: int, title: str | None, chat_type: str) -> None:
        """Insert or update chat."""
        if self.use_postgres:
            with self._pg_connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO chats(chat_id, title, chat_type, created_at, updated_at)
                    VALUES (%s, %s, %s, NOW(), NOW())
                    ON CONFLICT(chat_id) DO UPDATE SET
                        title=EXCLUDED.title,
                        chat_type=EXCLUDED.chat_type,
                        updated_at=NOW()
                    """,
                    (chat_id, title, chat_type),
                )
                cur.close()
        else:
            now = datetime.now(tz=timezone.utc).isoformat()
            with self._sqlite_connect() as conn:
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
        """List all chat IDs."""
        if self.use_postgres:
            with self._pg_connect() as conn:
                cur = conn.cursor()
                cur.execute("SELECT chat_id FROM chats WHERE is_active = TRUE")
                rows = cur.fetchall()
                cur.close()
                return [int(row[0]) for row in rows]
        else:
            with self._sqlite_connect() as conn:
                rows = conn.execute("SELECT chat_id FROM chats").fetchall()
            return [int(row["chat_id"]) for row in rows]

    def add_chat_message(self, chat_id: int, role: str, text: str) -> int:
        """
        Add a message to chat history.
        Returns the message ID.

        Note: PostgreSQL version does NOT limit to 30 messages.
        """
        text = text[:4000]  # Truncate long messages

        if self.use_postgres:
            with self._pg_connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO chat_messages(chat_id, role, text, created_at)
                    VALUES (%s, %s, %s, NOW())
                    RETURNING id
                    """,
                    (chat_id, role, text),
                )
                message_id = cur.fetchone()[0]
                cur.close()
                return message_id
        else:
            # SQLite version with 30 message limit
            now = datetime.now(tz=timezone.utc).isoformat()
            with self._sqlite_connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO chat_messages(chat_id, role, text, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (chat_id, role, text, now),
                )
                message_id = cursor.lastrowid

                # Delete old messages (keep last 30)
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
            return message_id

    def get_recent_chat_messages(self, chat_id: int, limit: int = 8) -> list[dict[str, str]]:
        """Get recent messages from chat."""
        if self.use_postgres:
            with self._pg_connect() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(
                    """
                    SELECT role, text
                    FROM chat_messages
                    WHERE chat_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (chat_id, limit),
                )
                rows = cur.fetchall()
                cur.close()
                return [
                    {"role": str(row["role"]), "text": str(row["text"])}
                    for row in reversed(rows)
                ]
        else:
            with self._sqlite_connect() as conn:
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
        """Save a driver request."""
        if self.use_postgres:
            with self._pg_connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO requests(user_id, full_name, username, request_type, details, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    RETURNING created_at
                    """,
                    (user_id, full_name, username, request_type, details),
                )
                created_at = cur.fetchone()[0].isoformat()
                cur.close()
        else:
            now = datetime.now(tz=timezone.utc).isoformat()
            created_at = now
            with self._sqlite_connect() as conn:
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
            created_at=created_at,
        )

    def get_last_message_id(self, chat_id: int) -> int | None:
        """Get the ID of the last message in a chat."""
        if self.use_postgres:
            with self._pg_connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id FROM chat_messages WHERE chat_id = %s ORDER BY id DESC LIMIT 1",
                    (chat_id,)
                )
                row = cur.fetchone()
                cur.close()
                return int(row[0]) if row else None
        else:
            with self._sqlite_connect() as conn:
                row = conn.execute(
                    "SELECT id FROM chat_messages WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
                    (chat_id,)
                ).fetchone()
            return int(row["id"]) if row else None

    # ========================================================================
    # RAG & Knowledge Base Methods (PostgreSQL only)
    # ========================================================================

    def add_kb_document(
        self,
        title: str,
        content: str,
        document_type: str,
        category: str | None = None,
        source_file: str | None = None,
    ) -> int:
        """Add a knowledge base document. Returns document ID."""
        if not self.use_postgres:
            raise NotImplementedError("KB documents require PostgreSQL")

        with self._pg_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO kb_documents(title, content, document_type, category, source_file, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id
                """,
                (title, content, document_type, category, source_file),
            )
            doc_id = cur.fetchone()[0]
            cur.close()
        return doc_id

    def add_kb_chunk(
        self,
        document_id: int,
        chunk_index: int,
        chunk_text: str,
        embedding: list[float],
        chunk_tokens: int | None = None,
    ) -> int:
        """Add a knowledge base chunk with embedding. Returns chunk ID."""
        if not self.use_postgres:
            raise NotImplementedError("KB chunks require PostgreSQL")

        with self._pg_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO kb_chunks(document_id, chunk_index, chunk_text, chunk_tokens, embedding, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                RETURNING id
                """,
                (document_id, chunk_index, chunk_text, chunk_tokens, embedding),
            )
            chunk_id = cur.fetchone()[0]
            cur.close()
        return chunk_id

    def vector_search_kb(
        self,
        embedding: list[float],
        top_k: int = 5,
        document_type: str | None = None,
    ) -> list[dict]:
        """
        Semantic search in knowledge base using vector similarity.
        Returns list of relevant chunks with metadata.
        """
        if not self.use_postgres:
            raise NotImplementedError("Vector search requires PostgreSQL with pgvector")

        with self._pg_connect() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Build query with optional document_type filter
            query = """
                SELECT
                    c.id,
                    c.chunk_text,
                    c.chunk_index,
                    d.title,
                    d.document_type,
                    d.category,
                    1 - (c.embedding <=> %s) AS similarity
                FROM kb_chunks c
                JOIN kb_documents d ON c.document_id = d.id
                WHERE d.is_active = TRUE
            """
            params: list = [embedding]

            if document_type:
                query += " AND d.document_type = %s"
                params.append(document_type)

            query += " ORDER BY c.embedding <=> %s LIMIT %s"
            params.extend([embedding, top_k])

            cur.execute(query, params)
            results = cur.fetchall()
            cur.close()

        return [dict(row) for row in results]

    def add_message_embedding(self, message_id: int, embedding: list[float]) -> None:
        """Store embedding for a message."""
        if not self.use_postgres:
            return  # Silently skip for SQLite

        with self._pg_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO message_embeddings(message_id, embedding, created_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT(message_id) DO UPDATE SET embedding = EXCLUDED.embedding
                """,
                (message_id, embedding),
            )
            cur.close()

    def vector_search_messages(
        self,
        chat_id: int,
        embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        """Semantic search in message history."""
        if not self.use_postgres:
            raise NotImplementedError("Vector search requires PostgreSQL")

        with self._pg_connect() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """
                SELECT
                    m.id,
                    m.role,
                    m.text,
                    m.created_at,
                    1 - (e.embedding <=> %s) AS similarity
                FROM message_embeddings e
                JOIN chat_messages m ON e.message_id = m.id
                WHERE m.chat_id = %s
                ORDER BY e.embedding <=> %s
                LIMIT %s
                """,
                (embedding, chat_id, embedding, top_k),
            )
            results = cur.fetchall()
            cur.close()
        return [dict(row) for row in results]

    # ========================================================================
    # Driver Profile Methods (PostgreSQL only)
    # ========================================================================

    def get_or_create_driver_profile(
        self,
        user_id: int,
        user_data: dict,
    ) -> dict:
        """Get or create driver profile."""
        if not self.use_postgres:
            # Return minimal profile for SQLite
            return {
                "user_id": user_id,
                "full_name": user_data.get("full_name", "Unknown"),
                "username": user_data.get("username"),
                "status": "active",
            }

        with self._pg_connect() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Try to get existing profile
            cur.execute("SELECT * FROM drivers WHERE user_id = %s", (user_id,))
            profile = cur.fetchone()

            if profile:
                cur.close()
                return dict(profile)

            # Create new profile
            cur.execute(
                """
                INSERT INTO drivers(user_id, full_name, username, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                RETURNING *
                """,
                (user_id, user_data.get("full_name", "Unknown"), user_data.get("username")),
            )
            profile = cur.fetchone()
            cur.close()

        return dict(profile)

    def update_driver_preference(
        self,
        user_id: int,
        preference_key: str,
        preference_value: str,
    ) -> None:
        """Update driver preference."""
        if not self.use_postgres:
            return  # Silently skip for SQLite

        with self._pg_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO driver_preferences(user_id, preference_key, preference_value, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                ON CONFLICT(user_id, preference_key) DO UPDATE SET
                    preference_value = EXCLUDED.preference_value,
                    updated_at = NOW()
                """,
                (user_id, preference_key, preference_value),
            )
            cur.close()

    def get_driver_preferences(self, user_id: int) -> dict[str, str]:
        """Get all preferences for a driver."""
        if not self.use_postgres:
            return {}

        with self._pg_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT preference_key, preference_value FROM driver_preferences WHERE user_id = %s",
                (user_id,)
            )
            rows = cur.fetchall()
            cur.close()

        return {row[0]: row[1] for row in rows}

    def add_driver_stat(
        self,
        user_id: int,
        stat_date: date,
        stat_type: str,
        stat_value: float,
    ) -> None:
        """Add/update driver statistic."""
        if not self.use_postgres:
            return  # Silently skip for SQLite

        with self._pg_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO driver_statistics(user_id, stat_date, stat_type, stat_value, created_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT(user_id, stat_date, stat_type) DO UPDATE SET
                    stat_value = EXCLUDED.stat_value
                """,
                (user_id, stat_date, stat_type, stat_value),
            )
            cur.close()

    def get_driver_stats(
        self,
        user_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        """Get driver statistics for a period."""
        if not self.use_postgres:
            return []

        with self._pg_connect() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            query = "SELECT * FROM driver_statistics WHERE user_id = %s"
            params: list = [user_id]

            if start_date:
                query += " AND stat_date >= %s"
                params.append(start_date)
            if end_date:
                query += " AND stat_date <= %s"
                params.append(end_date)

            query += " ORDER BY stat_date DESC"

            cur.execute(query, params)
            results = cur.fetchall()
            cur.close()

        return [dict(row) for row in results]

    # ========================================================================
    # Cleanup
    # ========================================================================

    def close(self) -> None:
        """Close database connections."""
        if self.use_postgres and hasattr(self, 'pg_pool'):
            self.pg_pool.closeall()
            logger.info("PostgreSQL connection pool closed")
