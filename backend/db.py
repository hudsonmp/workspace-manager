import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "workspace_manager.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS bundles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    space_index INTEGER,
    created_at TEXT NOT NULL,
    restored_at TEXT
);

CREATE TABLE IF NOT EXISTS tabs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bundle_id TEXT NOT NULL REFERENCES bundles(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    title TEXT,
    favicon_url TEXT,
    position INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS space_names (
    space_index INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
"""


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db


async def init_db():
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await db.commit()
    finally:
        await db.close()
