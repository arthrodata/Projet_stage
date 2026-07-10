from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DB_PATH = DATA_DIR / "app.db"
DEFAULT_ADMIN_EMAIL = "oussamaelbakkouri128@gmail.com"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def iter_connection() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with iter_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                first_name TEXT NOT NULL DEFAULT '',
                last_name TEXT NOT NULL DEFAULT '',
                password_hash TEXT NOT NULL,
                is_validated INTEGER NOT NULL DEFAULT 0,
                is_admin INTEGER NOT NULL DEFAULT 0,
                validated_at TEXT,
                validated_by INTEGER,
                last_login_at TEXT,
                last_activity_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                params_json TEXT NOT NULL,
                result_count INTEGER NOT NULL DEFAULT 0,
                results_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_search_history_user_created
                ON search_history(user_id, created_at DESC);
            """
        )
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "first_name" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN first_name TEXT NOT NULL DEFAULT ''")
        if "last_name" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN last_name TEXT NOT NULL DEFAULT ''")
        if "is_validated" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN is_validated INTEGER NOT NULL DEFAULT 0")
        if "is_admin" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        if "validated_at" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN validated_at TEXT")
        if "validated_by" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN validated_by INTEGER")
        if "last_login_at" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN last_login_at TEXT")
        if "last_activity_at" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN last_activity_at TEXT")

        admin_email = os.getenv("ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL).strip().lower()
        if admin_email:
            conn.execute(
                """
                UPDATE users
                SET is_admin = 1,
                    is_validated = 1,
                    validated_at = COALESCE(validated_at, CURRENT_TIMESTAMP)
                WHERE lower(email) = lower(?)
                """,
                (admin_email,),
            )
