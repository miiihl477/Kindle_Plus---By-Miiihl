"""
WriterFlow — Database Layer
===========================
Consolidates: connection, schema, all repositories, all services.

Sections
--------
1. Connection & Schema          (initialize_database, get_connection)
2. Repositories                 (Book, Chapter, Character, Location,
                                  Faction, Timeline, BrainDump, Goal,
                                  WritingSession, Settings)
3. Services / Business Logic    (BookService, ChapterService,
                                  CharacterService, WorldBuildingService,
                                  BrainDumpService, DashboardService,
                                  SettingsService)
4. Image utilities              (process_image, image_to_base64)

PostgreSQL migration path
─────────────────────────
• Replace get_connection() with a psycopg2/asyncpg pool context manager.
• Change ? placeholders to %s.
• Replace DATE('now') with CURRENT_DATE.
• Remove partial-index WHERE clauses or replace with filtered views.
• ALLOWED_TABLES and all service logic remain unchanged.
"""

import base64
import io
import logging
import os
import sqlite3
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from utils import count_words

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# 1. CONNECTION & SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

_env = os.environ.get("WRITERFLOW_DB", "").strip()
if _env:
    DB_PATH = _env
elif os.path.isdir("/tmp"):
    DB_PATH = "/tmp/writerflow.db"
else:
    DB_PATH = "writerflow.db"

logger.info("WriterFlow DB: %s", DB_PATH)

ALLOWED_TABLES = frozenset({
    "books", "chapters", "characters", "locations", "factions",
    "timeline_events", "brain_dumps", "goals", "writing_sessions",
    "app_settings",
})


@contextmanager
def get_connection():
    """Thread-safe SQLite connection using WAL mode."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _add_column_if_missing(
    table: str, column: str, col_type: str, backfill_from: str = None
) -> None:
    with get_connection() as conn:
        existing = {c[1] for c in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            if backfill_from and backfill_from in existing:
                conn.execute(f"UPDATE {table} SET {column} = {backfill_from}")
            logger.info("Migration: added %s.%s", table, column)


def initialize_database():
    """Create tables, run column migrations, then create indexes."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS books (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                synopsis    TEXT    DEFAULT '',
                genre       TEXT    DEFAULT '',
                status      TEXT    DEFAULT 'Planejamento',
                cover_image BLOB,
                cover_mime  TEXT    DEFAULT 'image/jpeg',
                word_count  INTEGER DEFAULT 0,
                deleted_at  TIMESTAMP,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS chapters (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id     INTEGER NOT NULL,
                title       TEXT    NOT NULL,
                content     TEXT    DEFAULT '',
                position    INTEGER DEFAULT 0,
                word_count  INTEGER DEFAULT 0,
                deleted_at  TIMESTAMP,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS characters (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id       INTEGER NOT NULL,
                name          TEXT    NOT NULL,
                role          TEXT    DEFAULT '',
                description   TEXT    DEFAULT '',
                photo         BLOB,
                photo_mime    TEXT    DEFAULT 'image/jpeg',
                relationships TEXT    DEFAULT '',
                notes         TEXT    DEFAULT '',
                deleted_at    TIMESTAMP,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS locations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id     INTEGER NOT NULL,
                name        TEXT    NOT NULL,
                description TEXT    DEFAULT '',
                notes       TEXT    DEFAULT '',
                deleted_at  TIMESTAMP,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS factions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id     INTEGER NOT NULL,
                name        TEXT    NOT NULL,
                description TEXT    DEFAULT '',
                notes       TEXT    DEFAULT '',
                deleted_at  TIMESTAMP,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS timeline_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id     INTEGER NOT NULL,
                title       TEXT    NOT NULL,
                description TEXT    DEFAULT '',
                date_label  TEXT    DEFAULT '',
                position    INTEGER DEFAULT 0,
                deleted_at  TIMESTAMP,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS brain_dumps (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id    INTEGER,
                content    TEXT    NOT NULL,
                tags       TEXT    DEFAULT '',
                deleted_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS goals (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_type    TEXT    NOT NULL,
                target_words INTEGER DEFAULT 0,
                period       TEXT    DEFAULT 'daily',
                active       INTEGER DEFAULT 1,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS writing_sessions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id       INTEGER,
                chapter_id    INTEGER,
                words_written INTEGER DEFAULT 0,
                session_date  DATE    DEFAULT (DATE('now')),
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS app_settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
        """)

    for table in ("books", "chapters", "characters", "locations",
                  "factions", "timeline_events", "brain_dumps"):
        _add_column_if_missing(table, "deleted_at", "TIMESTAMP")

    for table in ("locations", "factions", "timeline_events"):
        _add_column_if_missing(table, "updated_at", "TIMESTAMP",
                               backfill_from="created_at")

    with get_connection() as conn:
        conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_chapters_book
                ON chapters(book_id);
            CREATE INDEX IF NOT EXISTS idx_characters_book
                ON characters(book_id);
            CREATE INDEX IF NOT EXISTS idx_brain_dumps_book
                ON brain_dumps(book_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_date
                ON writing_sessions(session_date);
            CREATE INDEX IF NOT EXISTS idx_books_status
                ON books(status)       WHERE deleted_at IS NULL;
            CREATE INDEX IF NOT EXISTS idx_books_genre
                ON books(genre)        WHERE deleted_at IS NULL;
            CREATE INDEX IF NOT EXISTS idx_books_status_genre
                ON books(status, genre) WHERE deleted_at IS NULL;
            CREATE INDEX IF NOT EXISTS idx_chapters_active
                ON chapters(book_id, position) WHERE deleted_at IS NULL;
        """)

    logger.info("Database initialised at %s", DB_PATH)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. BASE REPOSITORY
# ═══════════════════════════════════════════════════════════════════════════════

_SAFE_ORDER_COLUMNS = frozenset({
    "id", "title", "name", "position", "created_at", "updated_at",
    "session_date", "period", "status", "genre", "deleted_at",
})


class BaseRepository(ABC):

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        table = getattr(cls, "table_name", None)
        if isinstance(table, str) and table not in ALLOWED_TABLES:
            raise ValueError(
                f"{cls.__name__}.table_name='{table}' is not in ALLOWED_TABLES."
            )

    @property
    @abstractmethod
    def table_name(self) -> str:
        pass

    def find_by_id(self, record_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table_name} "
                f"WHERE id = ? AND deleted_at IS NULL",
                (record_id,),
            ).fetchone()
            return dict(row) if row else None

    def find_all(self, order_by: str = "id") -> List[Dict]:
        if order_by not in _SAFE_ORDER_COLUMNS:
            raise ValueError(f"Unsafe order_by: '{order_by}'")
        with get_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM {self.table_name} "
                f"WHERE deleted_at IS NULL ORDER BY {order_by}"
            ).fetchall()
            return [dict(r) for r in rows]

    def soft_delete(self, record_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE {self.table_name} "
                f"SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
                f"WHERE id = ? AND deleted_at IS NULL",
                (record_id,),
            )
            affected = cursor.rowcount > 0
            if affected:
                logger.info("Soft-deleted %s id=%s", self.table_name, record_id)
            return affected

    def restore(self, record_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE {self.table_name} "
                f"SET deleted_at = NULL, updated_at = CURRENT_TIMESTAMP "
                f"WHERE id = ? AND deleted_at IS NOT NULL",
                (record_id,),
            )
            affected = cursor.rowcount > 0
            if affected:
                logger.info("Restored %s id=%s", self.table_name, record_id)
            return affected

    def find_deleted(self) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM {self.table_name} "
                f"WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def delete(self, record_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,)
            )
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("Hard-deleted %s id=%s", self.table_name, record_id)
            return deleted

    def _build_update_query(self, record_id: int, data: Dict[str, Any]) -> bool:
        if not data:
            return False
        data["updated_at"] = "CURRENT_TIMESTAMP"
        set_clause = ", ".join(
            f"{k} = CURRENT_TIMESTAMP" if v == "CURRENT_TIMESTAMP" else f"{k} = ?"
            for k, v in data.items()
        )
        values = [v for v in data.values() if v != "CURRENT_TIMESTAMP"]
        values.append(record_id)
        with get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE {self.table_name} SET {set_clause} WHERE id = ?",
                values,
            )
            return cursor.rowcount > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 3. REPOSITORIES
# ═══════════════════════════════════════════════════════════════════════════════

class BookRepository(BaseRepository):
    table_name = "books"

    def create(self, title, synopsis="", genre="", status="Planejamento",
               cover_image=None, cover_mime="image/jpeg") -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO books (title,synopsis,genre,status,cover_image,cover_mime) "
                "VALUES (?,?,?,?,?,?)",
                (title, synopsis, genre, status, cover_image, cover_mime),
            )
            book_id = cursor.lastrowid
            logger.info("Created book id=%s title=%r", book_id, title)
            return book_id

    def update(self, book_id: int, **kwargs) -> bool:
        allowed = {"title", "synopsis", "genre", "status",
                   "cover_image", "cover_mime", "word_count"}
        data = {k: v for k, v in kwargs.items() if k in allowed}
        return self._build_update_query(book_id, data)

    def search(self, query="", genre=None, status=None) -> List[Dict]:
        sql = "SELECT * FROM books WHERE deleted_at IS NULL"
        params: list = []
        if query:
            sql += " AND (title LIKE ? OR synopsis LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])
        if genre:
            sql += " AND genre = ?"
            params.append(genre)
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY updated_at DESC"
        with get_connection() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def list_lightweight(self) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id,title,synopsis,genre,status,word_count,created_at,updated_at "
                "FROM books WHERE deleted_at IS NULL ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_genres(self) -> List[str]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT genre FROM books "
                "WHERE genre!='' AND deleted_at IS NULL ORDER BY genre"
            ).fetchall()
            return [r[0] for r in rows]

    def recalculate_word_count(self, book_id: int) -> int:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(word_count),0) FROM chapters "
                "WHERE book_id=? AND deleted_at IS NULL",
                (book_id,),
            ).fetchone()
            total = row[0] if row else 0
            conn.execute(
                "UPDATE books SET word_count=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (total, book_id),
            )
            return total

    def get_stats(self) -> Dict:
        with get_connection() as conn:
            total_books    = conn.execute("SELECT COUNT(*) FROM books WHERE deleted_at IS NULL").fetchone()[0]
            total_chapters = conn.execute("SELECT COUNT(*) FROM chapters WHERE deleted_at IS NULL").fetchone()[0]
            total_words    = conn.execute("SELECT COALESCE(SUM(word_count),0) FROM books WHERE deleted_at IS NULL").fetchone()[0]
            by_status_rows = conn.execute(
                "SELECT status,COUNT(*) as cnt FROM books WHERE deleted_at IS NULL GROUP BY status"
            ).fetchall()
        return {
            "total_books":    total_books,
            "total_chapters": total_chapters,
            "total_words":    total_words,
            "by_status":      {r["status"]: r["cnt"] for r in by_status_rows},
        }

    def get_deleted_books(self) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id,title,genre,status,word_count,deleted_at "
                "FROM books WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]


class ChapterRepository(BaseRepository):
    table_name = "chapters"

    def create(self, book_id: int, title: str, content: str = "", position: int = None) -> int:
        wc = count_words(content)
        with get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if position is None:
                row = conn.execute(
                    "SELECT COALESCE(MAX(position),-1)+1 FROM chapters "
                    "WHERE book_id=? AND deleted_at IS NULL",
                    (book_id,),
                ).fetchone()
                position = row[0]
            cursor = conn.execute(
                "INSERT INTO chapters (book_id,title,content,position,word_count) VALUES (?,?,?,?,?)",
                (book_id, title, content, position, wc),
            )
            ch_id = cursor.lastrowid
            logger.info("Created chapter id=%s book_id=%s pos=%s", ch_id, book_id, position)
            return ch_id

    def find_by_book(self, book_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM chapters WHERE book_id=? AND deleted_at IS NULL ORDER BY position ASC",
                (book_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def find_by_book_lightweight(self, book_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id,book_id,title,position,word_count,created_at,updated_at "
                "FROM chapters WHERE book_id=? AND deleted_at IS NULL ORDER BY position ASC",
                (book_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def find_deleted_by_book(self, book_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id,book_id,title,word_count,deleted_at FROM chapters "
                "WHERE book_id=? AND deleted_at IS NOT NULL ORDER BY deleted_at DESC",
                (book_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_content(self, chapter_id: int, content: str) -> bool:
        wc = count_words(content)
        with get_connection() as conn:
            conn.execute(
                "UPDATE chapters SET content=?,word_count=?,updated_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND deleted_at IS NULL",
                (content, wc, chapter_id),
            )
            return True

    def get_word_count(self, chapter_id: int) -> int:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT word_count FROM chapters WHERE id=? AND deleted_at IS NULL",
                (chapter_id,),
            ).fetchone()
            return row["word_count"] if row else 0

    def update(self, chapter_id: int, **kwargs) -> bool:
        allowed = {"title", "content", "position", "word_count"}
        data = {k: v for k, v in kwargs.items() if k in allowed}
        if "content" in data:
            data["word_count"] = count_words(data["content"])
        return self._build_update_query(chapter_id, data)

    def reorder(self, book_id: int, ordered_ids: List[int]) -> bool:
        with get_connection() as conn:
            for pos, ch_id in enumerate(ordered_ids):
                conn.execute(
                    "UPDATE chapters SET position=? WHERE id=? AND book_id=? AND deleted_at IS NULL",
                    (pos, ch_id, book_id),
                )
            return True

    def get_total_words_for_book(self, book_id: int) -> int:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(word_count),0) FROM chapters "
                "WHERE book_id=? AND deleted_at IS NULL",
                (book_id,),
            ).fetchone()
            return row[0] if row else 0


class CharacterRepository(BaseRepository):
    table_name = "characters"

    def create(self, book_id, name, role="", description="",
               photo=None, photo_mime="image/jpeg",
               relationships="", notes="") -> int:
        with get_connection() as conn:
            c = conn.execute(
                "INSERT INTO characters "
                "(book_id,name,role,description,photo,photo_mime,relationships,notes) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (book_id, name, role, description, photo, photo_mime, relationships, notes),
            )
            return c.lastrowid

    def find_by_book(self, book_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM characters WHERE book_id=? AND deleted_at IS NULL ORDER BY name",
                (book_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update(self, char_id, **kwargs) -> bool:
        allowed = {"name","role","description","photo","photo_mime","relationships","notes"}
        return self._build_update_query(char_id, {k:v for k,v in kwargs.items() if k in allowed})

    def search(self, book_id: int, query: str) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM characters WHERE book_id=? AND deleted_at IS NULL "
                "AND (name LIKE ? OR description LIKE ? OR role LIKE ?) ORDER BY name",
                (book_id, f"%{query}%", f"%{query}%", f"%{query}%"),
            ).fetchall()
            return [dict(r) for r in rows]


class LocationRepository(BaseRepository):
    table_name = "locations"

    def create(self, book_id, name, description="", notes="") -> int:
        with get_connection() as conn:
            c = conn.execute(
                "INSERT INTO locations (book_id,name,description,notes) VALUES (?,?,?,?)",
                (book_id, name, description, notes),
            )
            return c.lastrowid

    def find_by_book(self, book_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM locations WHERE book_id=? AND deleted_at IS NULL ORDER BY name",
                (book_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update(self, loc_id, **kwargs) -> bool:
        allowed = {"name","description","notes"}
        return self._build_update_query(loc_id, {k:v for k,v in kwargs.items() if k in allowed})

    def search(self, book_id: int, query: str) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM locations WHERE book_id=? AND deleted_at IS NULL "
                "AND (name LIKE ? OR description LIKE ?) ORDER BY name",
                (book_id, f"%{query}%", f"%{query}%"),
            ).fetchall()
            return [dict(r) for r in rows]


class FactionRepository(BaseRepository):
    table_name = "factions"

    def create(self, book_id, name, description="", notes="") -> int:
        with get_connection() as conn:
            c = conn.execute(
                "INSERT INTO factions (book_id,name,description,notes) VALUES (?,?,?,?)",
                (book_id, name, description, notes),
            )
            return c.lastrowid

    def find_by_book(self, book_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM factions WHERE book_id=? AND deleted_at IS NULL ORDER BY name",
                (book_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update(self, fac_id, **kwargs) -> bool:
        allowed = {"name","description","notes"}
        return self._build_update_query(fac_id, {k:v for k,v in kwargs.items() if k in allowed})


class TimelineRepository(BaseRepository):
    table_name = "timeline_events"

    def create(self, book_id, title, description="", date_label="", position=None) -> int:
        with get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if position is None:
                row = conn.execute(
                    "SELECT COALESCE(MAX(position),-1)+1 FROM timeline_events "
                    "WHERE book_id=? AND deleted_at IS NULL", (book_id,)
                ).fetchone()
                position = row[0]
            c = conn.execute(
                "INSERT INTO timeline_events (book_id,title,description,date_label,position) "
                "VALUES (?,?,?,?,?)",
                (book_id, title, description, date_label, position),
            )
            return c.lastrowid

    def find_by_book(self, book_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM timeline_events WHERE book_id=? AND deleted_at IS NULL ORDER BY position",
                (book_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update(self, ev_id, **kwargs) -> bool:
        allowed = {"title","description","date_label","position"}
        return self._build_update_query(ev_id, {k:v for k,v in kwargs.items() if k in allowed})


class BrainDumpRepository(BaseRepository):
    table_name = "brain_dumps"

    def create(self, content, book_id=None, tags="") -> int:
        with get_connection() as conn:
            c = conn.execute(
                "INSERT INTO brain_dumps (content,book_id,tags) VALUES (?,?,?)",
                (content, book_id, tags),
            )
            return c.lastrowid

    def find_all_with_filter(self, query="", book_id=None, tag=None) -> List[Dict]:
        sql = "SELECT * FROM brain_dumps WHERE deleted_at IS NULL"
        params: list = []
        if book_id:
            sql += " AND book_id=?"; params.append(book_id)
        if query:
            sql += " AND (content LIKE ? OR tags LIKE ?)"; params.extend([f"%{query}%"]*2)
        if tag:
            sql += " AND tags LIKE ?"; params.append(f"%{tag}%")
        sql += " ORDER BY created_at DESC"
        with get_connection() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def update(self, dump_id, content, tags) -> bool:
        with get_connection() as conn:
            conn.execute(
                "UPDATE brain_dumps SET content=?,tags=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (content, tags, dump_id),
            )
            return True

    def get_all_tags(self) -> List[str]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT tags FROM brain_dumps WHERE tags!='' AND deleted_at IS NULL"
            ).fetchall()
        tags: set = set()
        for r in rows:
            for t in r["tags"].split(","):
                t = t.strip()
                if t:
                    tags.add(t)
        return sorted(tags)


class GoalRepository(BaseRepository):
    table_name = "goals"

    def insert(self, goal_type, target_words, period) -> int:
        with get_connection() as conn:
            c = conn.execute(
                "INSERT INTO goals (goal_type,target_words,period,active) VALUES (?,?,?,1)",
                (goal_type, target_words, period),
            )
            return c.lastrowid

    def deactivate_by_period(self, period) -> None:
        with get_connection() as conn:
            conn.execute("UPDATE goals SET active=0 WHERE period=?", (period,))

    def get_active_goals(self) -> List[Dict]:
        with get_connection() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM goals WHERE active=1").fetchall()]


class WritingSessionRepository(BaseRepository):
    table_name = "writing_sessions"

    def log_session(self, words_written, book_id=None, chapter_id=None) -> int:
        with get_connection() as conn:
            c = conn.execute(
                "INSERT INTO writing_sessions (book_id,chapter_id,words_written) VALUES (?,?,?)",
                (book_id, chapter_id, words_written),
            )
            return c.lastrowid

    def get_words_today(self) -> int:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(words_written),0) FROM writing_sessions "
                "WHERE session_date=DATE('now')"
            ).fetchone()
            return row[0] if row else 0

    def get_words_this_month(self) -> int:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(words_written),0) FROM writing_sessions "
                "WHERE strftime('%Y-%m',session_date)=strftime('%Y-%m','now')"
            ).fetchone()
            return row[0] if row else 0

    def get_daily_words_last_30_days(self) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT session_date, SUM(words_written) as total FROM writing_sessions "
                "WHERE session_date>=DATE('now','-30 days') "
                "GROUP BY session_date ORDER BY session_date"
            ).fetchall()
            return [dict(r) for r in rows]


class SettingsRepository:
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key=?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def set(self, key: str, value: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO app_settings (key,value) VALUES (?,?)",
                (key, value),
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. IMAGE UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def process_image(uploaded_file, max_size: Tuple[int, int] = (400, 600)) -> Tuple[bytes, str]:
    """Resize and compress uploaded image to JPEG."""
    img = Image.open(uploaded_file)
    img.thumbnail(max_size, Image.LANCZOS)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue(), "image/jpeg"


def image_to_base64(image_bytes: bytes) -> str:
    if not image_bytes:
        return ""
    return f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode()}"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. SERVICES (business logic / orchestration)
# ═══════════════════════════════════════════════════════════════════════════════

# Module-level repository singletons (stateless — safe to share)
_book_repo     = BookRepository()
_chapter_repo  = ChapterRepository()
_char_repo     = CharacterRepository()
_loc_repo      = LocationRepository()
_faction_repo  = FactionRepository()
_timeline_repo = TimelineRepository()
_brain_repo    = BrainDumpRepository()
_goal_repo     = GoalRepository()
_session_repo  = WritingSessionRepository()
_settings_repo = SettingsRepository()


class BookService:

    def create_book(self, title, synopsis="", genre="",
                    status="Planejamento", cover_file=None) -> int:
        cover_bytes, mime = None, "image/jpeg"
        if cover_file:
            cover_bytes, mime = process_image(cover_file, (400, 600))
        return _book_repo.create(title, synopsis, genre, status, cover_bytes, mime)

    def update_book(self, book_id: int, cover_file=None, **kwargs) -> bool:
        if cover_file:
            cover_bytes, mime = process_image(cover_file, (400, 600))
            kwargs["cover_image"] = cover_bytes
            kwargs["cover_mime"]  = mime
        return _book_repo.update(book_id, **kwargs)

    def soft_delete_book(self, book_id: int) -> bool:
        return _book_repo.soft_delete(book_id)

    def restore_book(self, book_id: int) -> bool:
        return _book_repo.restore(book_id)

    def delete_book(self, book_id: int) -> bool:
        return _book_repo.delete(book_id)

    def get_deleted_books(self) -> List[Dict]:
        return _book_repo.get_deleted_books()

    def get_book(self, book_id: int) -> Optional[Dict]:
        return _book_repo.find_by_id(book_id)

    def list_books(self, query="", genre=None, status=None) -> List[Dict]:
        return _book_repo.search(query, genre, status)

    def list_books_lightweight(self) -> List[Dict]:
        return _book_repo.list_lightweight()

    def get_all_genres(self) -> List[str]:
        return _book_repo.get_all_genres()

    def get_stats(self) -> Dict:
        return _book_repo.get_stats()

    def refresh_word_count(self, book_id: int) -> int:
        return _book_repo.recalculate_word_count(book_id)


class ChapterService:

    def create_chapter(self, book_id: int, title: str) -> int:
        ch_id = _chapter_repo.create(book_id, title)
        _book_repo.recalculate_word_count(book_id)
        return ch_id

    def get_chapters(self, book_id: int) -> List[Dict]:
        return _chapter_repo.find_by_book(book_id)

    def get_chapters_lightweight(self, book_id: int) -> List[Dict]:
        return _chapter_repo.find_by_book_lightweight(book_id)

    def get_chapter(self, chapter_id: int) -> Optional[Dict]:
        return _chapter_repo.find_by_id(chapter_id)

    def save_content(self, chapter_id: int, content: str, book_id: int) -> bool:
        previous_wc = _chapter_repo.get_word_count(chapter_id)
        ok = _chapter_repo.update_content(chapter_id, content)
        if ok:
            _book_repo.recalculate_word_count(book_id)
            new_wc = count_words(content)
            delta  = new_wc - previous_wc
            if delta > 0:
                _session_repo.log_session(delta, book_id, chapter_id)
                logger.info("Session +%d words chapter_id=%s book_id=%s",
                            delta, chapter_id, book_id)
        return ok

    def update_chapter(self, chapter_id: int, **kwargs) -> bool:
        return _chapter_repo.update(chapter_id, **kwargs)

    def soft_delete_chapter(self, chapter_id: int, book_id: int) -> bool:
        ok = _chapter_repo.soft_delete(chapter_id)
        if ok:
            _book_repo.recalculate_word_count(book_id)
        return ok

    def restore_chapter(self, chapter_id: int, book_id: int) -> bool:
        ok = _chapter_repo.restore(chapter_id)
        if ok:
            _book_repo.recalculate_word_count(book_id)
        return ok

    def delete_chapter(self, chapter_id: int, book_id: int) -> bool:
        ok = _chapter_repo.delete(chapter_id)
        if ok:
            _book_repo.recalculate_word_count(book_id)
        return ok

    def get_deleted_chapters(self, book_id: int) -> List[Dict]:
        return _chapter_repo.find_deleted_by_book(book_id)

    def reorder_chapters(self, book_id: int, ordered_ids: List[int]) -> bool:
        return _chapter_repo.reorder(book_id, ordered_ids)


class CharacterService:

    def create(self, book_id, name, role="", description="",
               photo_file=None, relationships="", notes="") -> int:
        photo_bytes, mime = None, "image/jpeg"
        if photo_file:
            photo_bytes, mime = process_image(photo_file, (300, 300))
        return _char_repo.create(book_id, name, role, description,
                                 photo_bytes, mime, relationships, notes)

    def get_characters(self, book_id: int) -> List[Dict]:
        return _char_repo.find_by_book(book_id)

    def get_character(self, char_id: int) -> Optional[Dict]:
        return _char_repo.find_by_id(char_id)

    def update(self, char_id: int, photo_file=None, **kwargs) -> bool:
        if photo_file:
            photo_bytes, mime = process_image(photo_file, (300, 300))
            kwargs["photo"]      = photo_bytes
            kwargs["photo_mime"] = mime
        return _char_repo.update(char_id, **kwargs)

    def delete(self, char_id: int) -> bool:
        return _char_repo.soft_delete(char_id)

    def search(self, book_id: int, query: str) -> List[Dict]:
        return _char_repo.search(book_id, query)


class WorldBuildingService:

    def create_location(self, book_id, name, description="", notes="") -> int:
        return _loc_repo.create(book_id, name, description, notes)

    def get_locations(self, book_id) -> List[Dict]:
        return _loc_repo.find_by_book(book_id)

    def update_location(self, loc_id, **kwargs) -> bool:
        return _loc_repo.update(loc_id, **kwargs)

    def delete_location(self, loc_id) -> bool:
        return _loc_repo.soft_delete(loc_id)

    def search_locations(self, book_id, query) -> List[Dict]:
        return _loc_repo.search(book_id, query)

    def create_faction(self, book_id, name, description="", notes="") -> int:
        return _faction_repo.create(book_id, name, description, notes)

    def get_factions(self, book_id) -> List[Dict]:
        return _faction_repo.find_by_book(book_id)

    def update_faction(self, fac_id, **kwargs) -> bool:
        return _faction_repo.update(fac_id, **kwargs)

    def delete_faction(self, fac_id) -> bool:
        return _faction_repo.soft_delete(fac_id)

    def create_event(self, book_id, title, description="", date_label="") -> int:
        return _timeline_repo.create(book_id, title, description, date_label)

    def get_events(self, book_id) -> List[Dict]:
        return _timeline_repo.find_by_book(book_id)

    def update_event(self, ev_id, **kwargs) -> bool:
        return _timeline_repo.update(ev_id, **kwargs)

    def delete_event(self, ev_id) -> bool:
        return _timeline_repo.delete(ev_id)


class BrainDumpService:

    def create(self, content: str, book_id: int = None, tags: str = "") -> int:
        return _brain_repo.create(content, book_id, tags)

    def list(self, query="", book_id=None, tag=None) -> List[Dict]:
        return _brain_repo.find_all_with_filter(query, book_id, tag)

    def update(self, dump_id: int, content: str, tags: str) -> bool:
        return _brain_repo.update(dump_id, content, tags)

    def delete(self, dump_id: int) -> bool:
        return _brain_repo.soft_delete(dump_id)

    def get_all_tags(self) -> List[str]:
        return _brain_repo.get_all_tags()


class DashboardService:

    def get_dashboard_data(self) -> Dict:
        stats       = _book_repo.get_stats()
        words_today = _session_repo.get_words_today()
        words_month = _session_repo.get_words_this_month()
        daily_data  = _session_repo.get_daily_words_last_30_days()
        goals       = _goal_repo.get_active_goals()

        daily_goal   = next((g["target_words"] for g in goals if g["period"] == "daily"),   1000)
        monthly_goal = next((g["target_words"] for g in goals if g["period"] == "monthly"), 30000)

        return {
            **stats,
            "words_today":      words_today,
            "words_month":      words_month,
            "daily_data":       daily_data,
            "goals":            goals,
            "daily_goal":       daily_goal,
            "monthly_goal":     monthly_goal,
            "daily_progress":   min(100, int(words_today / daily_goal   * 100)) if daily_goal   else 0,
            "monthly_progress": min(100, int(words_month / monthly_goal * 100)) if monthly_goal else 0,
        }

    def save_goal(self, target_words: int, period: str) -> int:
        _goal_repo.deactivate_by_period(period)
        return _goal_repo.insert(goal_type="writing", target_words=target_words, period=period)

    def get_active_goals(self) -> List[Dict]:
        return _goal_repo.get_active_goals()

    def log_words(self, words: int, book_id: int = None, chapter_id: int = None) -> None:
        if words > 0:
            _session_repo.log_session(words, book_id, chapter_id)


class SettingsService:

    def get(self, key: str, default: str = None) -> Optional[str]:
        return _settings_repo.get(key, default)

    def set(self, key: str, value: str) -> None:
        _settings_repo.set(key, value)

    def get_kindle_position(self) -> Tuple[Optional[int], int]:
        raw_book = self.get("kindle_book_id")
        raw_idx  = self.get("kindle_chapter_idx", "0")
        book_id  = int(raw_book) if raw_book else None
        ch_idx   = int(raw_idx) if raw_idx else 0
        return book_id, ch_idx

    def save_kindle_position(self, book_id: int, chapter_idx: int) -> None:
        self.set("kindle_book_id",    str(book_id))
        self.set("kindle_chapter_idx", str(chapter_idx))
