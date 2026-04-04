#!/usr/bin/env python3
"""
Migration script: SQLite → PostgreSQL (Supabase)

Usage:
    python scripts/migrate_to_supabase.py --sqlite-path bot_data.sqlite3 --postgres-url postgresql://...
    python scripts/migrate_to_supabase.py --dry-run  # Test without writing
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from datetime import datetime, timezone

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


class MigrationStats:
    def __init__(self):
        self.chats_migrated = 0
        self.requests_migrated = 0
        self.messages_migrated = 0
        self.errors = 0


def migrate_chats(sqlite_conn, pg_conn, dry_run: bool = False) -> int:
    """Migrate chats table."""
    sqlite_cur = sqlite_conn.cursor()
    pg_cur = pg_conn.cursor()

    sqlite_cur.execute("SELECT chat_id, title, chat_type, created_at FROM chats")
    rows = sqlite_cur.fetchall()

    logger.info(f"Found {len(rows)} chats in SQLite")

    migrated = 0
    for row in rows:
        chat_id, title, chat_type, created_at = row

        if not dry_run:
            pg_cur.execute(
                """
                INSERT INTO chats(chat_id, title, chat_type, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, TRUE, %s, %s)
                ON CONFLICT(chat_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    chat_type = EXCLUDED.chat_type,
                    updated_at = EXCLUDED.updated_at
                """,
                (chat_id, title, chat_type, created_at, created_at),
            )
        migrated += 1

    if not dry_run:
        pg_conn.commit()

    sqlite_cur.close()
    pg_cur.close()

    logger.info(f"Migrated {migrated} chats")
    return migrated


def migrate_requests(sqlite_conn, pg_conn, dry_run: bool = False) -> int:
    """Migrate requests table."""
    sqlite_cur = sqlite_conn.cursor()
    pg_cur = pg_conn.cursor()

    sqlite_cur.execute(
        "SELECT id, user_id, full_name, username, request_type, details, created_at FROM requests"
    )
    rows = sqlite_cur.fetchall()

    logger.info(f"Found {len(rows)} requests in SQLite")

    migrated = 0
    for row in rows:
        req_id, user_id, full_name, username, request_type, details, created_at = row

        if not dry_run:
            # Note: SQLite auto-increment ID might conflict, so we let PostgreSQL generate new IDs
            pg_cur.execute(
                """
                INSERT INTO requests(user_id, full_name, username, request_type, details, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s)
                """,
                (user_id, full_name, username, request_type, details, created_at, created_at),
            )
        migrated += 1

    if not dry_run:
        pg_conn.commit()

    sqlite_cur.close()
    pg_cur.close()

    logger.info(f"Migrated {migrated} requests")
    return migrated


def migrate_chat_messages(sqlite_conn, pg_conn, dry_run: bool = False) -> int:
    """Migrate chat_messages table."""
    sqlite_cur = sqlite_conn.cursor()
    pg_cur = pg_conn.cursor()

    sqlite_cur.execute(
        "SELECT id, chat_id, role, text, created_at FROM chat_messages ORDER BY id"
    )
    rows = sqlite_cur.fetchall()

    logger.info(f"Found {len(rows)} chat messages in SQLite")

    migrated = 0
    for row in rows:
        msg_id, chat_id, role, text, created_at = row

        if not dry_run:
            pg_cur.execute(
                """
                INSERT INTO chat_messages(chat_id, role, text, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (chat_id, role, text, created_at),
            )
        migrated += 1

        if migrated % 1000 == 0:
            logger.info(f"Migrated {migrated} messages...")
            if not dry_run:
                pg_conn.commit()

    if not dry_run:
        pg_conn.commit()

    sqlite_cur.close()
    pg_cur.close()

    logger.info(f"Migrated {migrated} chat messages")
    return migrated


def validate_migration(sqlite_conn, pg_conn) -> bool:
    """Validate migration by comparing counts."""
    logger.info("Validating migration...")

    tables = ["chats", "requests", "chat_messages"]
    valid = True

    for table in tables:
        # SQLite count
        sqlite_cur = sqlite_conn.cursor()
        sqlite_cur.execute(f"SELECT COUNT(*) FROM {table}")
        sqlite_count = sqlite_cur.fetchone()[0]
        sqlite_cur.close()

        # PostgreSQL count
        pg_cur = pg_conn.cursor()
        pg_cur.execute(f"SELECT COUNT(*) FROM {table}")
        pg_count = pg_cur.fetchone()[0]
        pg_cur.close()

        match = "✓" if sqlite_count == pg_count else "✗"
        logger.info(f"{match} {table}: SQLite={sqlite_count}, PostgreSQL={pg_count}")

        if sqlite_count != pg_count:
            valid = False

    return valid


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite data to PostgreSQL")
    parser.add_argument(
        "--sqlite-path",
        default="bot_data.sqlite3",
        help="Path to SQLite database (default: bot_data.sqlite3)",
    )
    parser.add_argument(
        "--postgres-url",
        required=True,
        help="PostgreSQL connection URL (e.g., postgresql://user:pass@host:5432/dbname)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test migration without writing to PostgreSQL",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip validation after migration",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("SQLite → PostgreSQL Migration")
    logger.info("=" * 60)
    logger.info(f"SQLite path: {args.sqlite_path}")
    logger.info(f"PostgreSQL URL: {args.postgres_url[:30]}...")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("=" * 60)

    # Connect to databases
    try:
        logger.info("Connecting to SQLite...")
        sqlite_conn = sqlite3.connect(args.sqlite_path)

        logger.info("Connecting to PostgreSQL...")
        pg_conn = psycopg2.connect(args.postgres_url)

        if args.dry_run:
            logger.warning("DRY RUN MODE - No data will be written to PostgreSQL")

        # Run migrations
        stats = MigrationStats()

        logger.info("\n--- Migrating chats ---")
        stats.chats_migrated = migrate_chats(sqlite_conn, pg_conn, dry_run=args.dry_run)

        logger.info("\n--- Migrating requests ---")
        stats.requests_migrated = migrate_requests(sqlite_conn, pg_conn, dry_run=args.dry_run)

        logger.info("\n--- Migrating chat_messages ---")
        stats.messages_migrated = migrate_chat_messages(sqlite_conn, pg_conn, dry_run=args.dry_run)

        # Validation
        if not args.dry_run and not args.skip_validation:
            logger.info("\n--- Validation ---")
            valid = validate_migration(sqlite_conn, pg_conn)
            if valid:
                logger.info("✓ Migration validated successfully!")
            else:
                logger.error("✗ Validation failed - counts do not match")
                sys.exit(1)

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Migration Summary")
        logger.info("=" * 60)
        logger.info(f"Chats: {stats.chats_migrated}")
        logger.info(f"Requests: {stats.requests_migrated}")
        logger.info(f"Messages: {stats.messages_migrated}")
        logger.info(f"Errors: {stats.errors}")
        logger.info("=" * 60)

        if args.dry_run:
            logger.info("✓ Dry run completed successfully")
        else:
            logger.info("✓ Migration completed successfully")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        if 'sqlite_conn' in locals():
            sqlite_conn.close()
        if 'pg_conn' in locals():
            pg_conn.close()


if __name__ == "__main__":
    main()
