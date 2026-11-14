import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import IntegrityError

import aiosqlite

logger = logging.getLogger(__name__)

ROLE_ADMIN = "admin"
ROLE_EDITOR = "editor"
ROLE_USER = "user"

_db: aiosqlite.Connection | None = None
_locks: dict[tuple[int, int], asyncio.Lock] = {}

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_chat_id INTEGER NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL REFERENCES chats(id),
    username TEXT,
    role TEXT NOT NULL CHECK (role IN ('admin', 'editor', 'user')),
    created_at TEXT NOT NULL,
    UNIQUE (chat_id, telegram_id)
);

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL REFERENCES chats(id),
    name TEXT NOT NULL,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE (chat_id, name)
);

CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL REFERENCES chats(id),
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('dz', 'note')),
    date TEXT NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_records_lookup
    ON records (chat_id, subject_id, kind, date);

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    file_id TEXT NOT NULL,
    file_type TEXT NOT NULL CHECK (file_type IN ('photo', 'document')),
    file_name TEXT,
    caption TEXT,
    uploaded_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attachments_record
    ON attachments (record_id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def can_edit(role: str | None) -> bool:
    return role in {ROLE_ADMIN, ROLE_EDITOR}


def is_admin(role: str | None) -> bool:
    return role == ROLE_ADMIN


def user_lock(chat_id: int, user_id: int) -> asyncio.Lock:
    key = (chat_id, user_id)
    lock = _locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _locks[key] = lock
    return lock


def get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("database is not initialized")
    return _db


async def init_db(path: str) -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None
    database_path = Path(path)
    if not database_path.is_absolute():
        database_path = Path.cwd() / database_path
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = await aiosqlite.connect(database_path, isolation_level=None, timeout=30)
    connection.row_factory = aiosqlite.Row
    await connection.execute("PRAGMA foreign_keys = ON")
    await connection.execute("PRAGMA journal_mode = WAL")
    await connection.executescript(SCHEMA)
    await connection.execute("PRAGMA foreign_keys = ON")
    _db = connection
    logger.info("database ready: %s", database_path)


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


async def execute(sql: str, params: tuple = ()) -> aiosqlite.Cursor:
    return await get_db().execute(sql, params)


async def fetchone(sql: str, params: tuple = ()) -> aiosqlite.Row | None:
    cursor = await get_db().execute(sql, params)
    return await cursor.fetchone()


async def fetchall(sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
    cursor = await get_db().execute(sql, params)
    return list(await cursor.fetchall())


@asynccontextmanager
async def transaction() -> AsyncIterator[None]:
    db = get_db()
    await db.execute("BEGIN IMMEDIATE")
    try:
        yield
        await db.commit()
    except Exception:
        await db.rollback()
        raise


async def get_chat(telegram_chat_id: int) -> aiosqlite.Row | None:
    return await fetchone(
        "SELECT * FROM chats WHERE telegram_chat_id = ?",
        (telegram_chat_id,),
    )


async def get_or_create_chat(telegram_chat_id: int) -> aiosqlite.Row:
    existing = await get_chat(telegram_chat_id)
    if existing is not None:
        return existing
    try:
        await execute(
            "INSERT INTO chats (telegram_chat_id, created_at) VALUES (?, ?)",
            (telegram_chat_id, now_iso()),
        )
    except IntegrityError:
        pass
    chat = await get_chat(telegram_chat_id)
    if chat is None:
        raise RuntimeError("chat was not created")
    return chat


async def get_user(internal_chat_id: int, telegram_id: int) -> aiosqlite.Row | None:
    return await fetchone(
        "SELECT * FROM users WHERE chat_id = ? AND telegram_id = ?",
        (internal_chat_id, telegram_id),
    )


async def get_user_by_username(internal_chat_id: int, username: str) -> aiosqlite.Row | None:
    return await fetchone(
        """
        SELECT * FROM users
        WHERE chat_id = ? AND username = ? COLLATE NOCASE
        """,
        (internal_chat_id, username),
    )


async def has_admin(internal_chat_id: int) -> bool:
    row = await fetchone(
        "SELECT 1 AS ok FROM users WHERE chat_id = ? AND role = 'admin' LIMIT 1",
        (internal_chat_id,),
    )
    return row is not None


async def set_role(internal_user_id: int, role: str) -> None:
    await execute(
        "UPDATE users SET role = ? WHERE id = ?",
        (role, internal_user_id),
    )


async def update_username(internal_user_id: int, username: str | None) -> None:
    await execute(
        "UPDATE users SET username = ? WHERE id = ?",
        (username, internal_user_id),
    )


async def save_user(
    internal_chat_id: int,
    telegram_id: int,
    username: str | None,
    *,
    role: str | None = None,
) -> aiosqlite.Row:
    existing = await get_user(internal_chat_id, telegram_id)
    if existing is None:
        try:
            await execute(
                """
                INSERT INTO users (telegram_id, chat_id, username, role, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    telegram_id,
                    internal_chat_id,
                    username,
                    role or ROLE_USER,
                    now_iso(),
                ),
            )
        except IntegrityError:
            existing = await get_user(internal_chat_id, telegram_id)
            if existing is None:
                raise
        else:
            created = await get_user(internal_chat_id, telegram_id)
            if created is None:
                raise RuntimeError("user was not created")
            return created
    if username != existing["username"]:
        await update_username(existing["id"], username)
    if role is not None and role != existing["role"]:
        await set_role(existing["id"], role)
    if username != existing["username"] or (role is not None and role != existing["role"]):
        updated = await get_user(internal_chat_id, telegram_id)
        if updated is None:
            raise RuntimeError("user disappeared")
        return updated
    return existing


async def ensure_member(
    telegram_chat_id: int,
    telegram_id: int,
    username: str | None,
) -> aiosqlite.Row:
    chat = await get_or_create_chat(telegram_chat_id)
    return await save_user(chat["id"], telegram_id, username)


async def promote_first_admin(
    telegram_chat_id: int,
    telegram_id: int,
    username: str | None,
    *,
    group_admin: bool,
) -> aiosqlite.Row:
    chat = await get_or_create_chat(telegram_chat_id)
    if group_admin and not await has_admin(chat["id"]):
        user = await save_user(chat["id"], telegram_id, username, role=ROLE_ADMIN)
        logger.info("admin assigned chat=%s user=%s", telegram_chat_id, telegram_id)
        return user
    return await save_user(chat["id"], telegram_id, username)
