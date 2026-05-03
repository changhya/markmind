import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

DB_PATH = Path.home() / ".markmind" / "data" / "markmind.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def db() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id           TEXT PRIMARY KEY,
                filename     TEXT NOT NULL,
                original_path TEXT NOT NULL,
                file_size    INTEGER,
                mime_type    TEXT,
                status       TEXT NOT NULL DEFAULT 'pending',
                progress     INTEGER DEFAULT 0,
                error_message TEXT,
                wiki_pages_count INTEGER DEFAULT 0,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS wiki_pages (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                summary     TEXT,
                tags        TEXT DEFAULT '[]',
                content     TEXT NOT NULL,
                file_path   TEXT,
                parent_id   TEXT,
                document_id TEXT,
                chroma_id   TEXT,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                FOREIGN KEY (parent_id)   REFERENCES wiki_pages(id)
            );

            CREATE TABLE IF NOT EXISTS wiki_revisions (
                id           TEXT PRIMARY KEY,
                wiki_page_id TEXT NOT NULL,
                content      TEXT NOT NULL,
                summary      TEXT,
                revised_by   TEXT DEFAULT 'user',
                created_at   TEXT NOT NULL,
                FOREIGN KEY (wiki_page_id) REFERENCES wiki_pages(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chat_sessions (
                id           TEXT PRIMARY KEY,
                query        TEXT NOT NULL,
                response     TEXT NOT NULL,
                sources      TEXT DEFAULT '[]',
                context_used TEXT DEFAULT '[]',
                model        TEXT NOT NULL,
                created_at   TEXT NOT NULL
            );
        """)


def now_iso() -> str:
    return datetime.now().isoformat()


def new_id() -> str:
    return str(uuid.uuid4())
