from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Iterable

import aiosqlite


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._write_lock = asyncio.Lock()
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[aiosqlite.Connection]:
        db = await aiosqlite.connect(self.path)
        db.row_factory = aiosqlite.Row
        try:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("PRAGMA journal_mode = WAL")
            await db.execute("PRAGMA busy_timeout = 5000")
            yield db
        finally:
            await db.close()

    async def initialize(self) -> None:
        async with self._write_lock:
            async with self.connect() as db:
                await db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS guild_settings (
                        guild_id TEXT PRIMARY KEY,
                        command_channel_id TEXT,
                        staff_role_id TEXT,
                        created_at TEXT,
                        updated_at TEXT
                    );

                    CREATE TABLE IF NOT EXISTS containers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id TEXT NOT NULL,
                        owner_id TEXT NOT NULL,
                        container_name TEXT NOT NULL,
                        category_id TEXT,
                        terminal_channel_id TEXT,
                        logs_channel_id TEXT,
                        general_channel_id TEXT,
                        voice_channel_id TEXT,
                        status TEXT NOT NULL,
                        visibility TEXT NOT NULL,
                        inspection_active INTEGER DEFAULT 0,
                        suspended_reason TEXT,
                        created_at TEXT,
                        updated_at TEXT,
                        UNIQUE(guild_id, owner_id)
                    );

                    CREATE TABLE IF NOT EXISTS container_channels (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id TEXT NOT NULL,
                        owner_id TEXT NOT NULL,
                        channel_id TEXT NOT NULL,
                        channel_name TEXT NOT NULL,
                        channel_type TEXT NOT NULL,
                        is_system INTEGER DEFAULT 0,
                        created_at TEXT
                    );

                    CREATE UNIQUE INDEX IF NOT EXISTS idx_container_channels_channel
                    ON container_channels(guild_id, channel_id);

                    CREATE TABLE IF NOT EXISTS container_invites (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id TEXT NOT NULL,
                        owner_id TEXT NOT NULL,
                        invited_user_id TEXT NOT NULL,
                        created_at TEXT,
                        UNIQUE(guild_id, owner_id, invited_user_id)
                    );
                    """
                )
                await db.commit()

    async def upsert_guild_settings(self, guild_id: int, command_channel_id: int, staff_role_id: int) -> None:
        now = utcnow_iso()
        async with self._write_lock:
            async with self.connect() as db:
                await db.execute(
                    """
                    INSERT INTO guild_settings (guild_id, command_channel_id, staff_role_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        command_channel_id = excluded.command_channel_id,
                        staff_role_id = excluded.staff_role_id,
                        updated_at = excluded.updated_at
                    """,
                    (str(guild_id), str(command_channel_id), str(staff_role_id), now, now),
                )
                await db.commit()

    async def get_guild_settings(self, guild_id: int) -> aiosqlite.Row | None:
        async with self.connect() as db:
            async with db.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (str(guild_id),)) as cur:
                return await cur.fetchone()

    async def create_container(
        self,
        *,
        guild_id: int,
        owner_id: int,
        container_name: str,
        category_id: int | None,
        terminal_channel_id: int | None,
        logs_channel_id: int | None,
        general_channel_id: int | None,
        voice_channel_id: int | None,
        status: str,
        visibility: str,
    ) -> int:
        now = utcnow_iso()
        async with self._write_lock:
            async with self.connect() as db:
                cur = await db.execute(
                    """
                    INSERT INTO containers (
                        guild_id, owner_id, container_name, category_id,
                        terminal_channel_id, logs_channel_id, general_channel_id, voice_channel_id,
                        status, visibility, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(guild_id),
                        str(owner_id),
                        container_name,
                        str(category_id) if category_id else None,
                        str(terminal_channel_id) if terminal_channel_id else None,
                        str(logs_channel_id) if logs_channel_id else None,
                        str(general_channel_id) if general_channel_id else None,
                        str(voice_channel_id) if voice_channel_id else None,
                        status,
                        visibility,
                        now,
                        now,
                    ),
                )
                await db.commit()
                return int(cur.lastrowid)

    async def get_container(self, guild_id: int, owner_id: int) -> aiosqlite.Row | None:
        async with self.connect() as db:
            async with db.execute(
                "SELECT * FROM containers WHERE guild_id = ? AND owner_id = ?",
                (str(guild_id), str(owner_id)),
            ) as cur:
                return await cur.fetchone()

    async def get_container_by_category(self, guild_id: int, category_id: int) -> aiosqlite.Row | None:
        async with self.connect() as db:
            async with db.execute(
                "SELECT * FROM containers WHERE guild_id = ? AND category_id = ?",
                (str(guild_id), str(category_id)),
            ) as cur:
                return await cur.fetchone()

    async def update_container(self, guild_id: int, owner_id: int, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = utcnow_iso()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = [str(value) if value is not None and key.endswith("_id") else value for key, value in fields.items()]
        values.extend([str(guild_id), str(owner_id)])
        async with self._write_lock:
            async with self.connect() as db:
                await db.execute(
                    f"UPDATE containers SET {assignments} WHERE guild_id = ? AND owner_id = ?",
                    values,
                )
                await db.commit()

    async def delete_container(self, guild_id: int, owner_id: int) -> None:
        async with self._write_lock:
            async with self.connect() as db:
                await db.execute("DELETE FROM container_invites WHERE guild_id = ? AND owner_id = ?", (str(guild_id), str(owner_id)))
                await db.execute("DELETE FROM container_channels WHERE guild_id = ? AND owner_id = ?", (str(guild_id), str(owner_id)))
                await db.execute("DELETE FROM containers WHERE guild_id = ? AND owner_id = ?", (str(guild_id), str(owner_id)))
                await db.commit()

    async def list_guild_containers(self, guild_id: int) -> list[aiosqlite.Row]:
        async with self.connect() as db:
            async with db.execute(
                "SELECT * FROM containers WHERE guild_id = ? ORDER BY id ASC",
                (str(guild_id),),
            ) as cur:
                return await cur.fetchall()

    async def add_container_channel(
        self,
        guild_id: int,
        owner_id: int,
        channel_id: int,
        channel_name: str,
        channel_type: str,
        is_system: bool = False,
    ) -> None:
        async with self._write_lock:
            async with self.connect() as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO container_channels
                    (guild_id, owner_id, channel_id, channel_name, channel_type, is_system, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (str(guild_id), str(owner_id), str(channel_id), channel_name, channel_type, int(is_system), utcnow_iso()),
                )
                await db.commit()

    async def add_many_container_channels(self, guild_id: int, owner_id: int, channels: Iterable[tuple[int, str, str, bool]]) -> None:
        async with self._write_lock:
            async with self.connect() as db:
                await db.executemany(
                    """
                    INSERT OR REPLACE INTO container_channels
                    (guild_id, owner_id, channel_id, channel_name, channel_type, is_system, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (str(guild_id), str(owner_id), str(channel_id), channel_name, channel_type, int(is_system), utcnow_iso())
                        for channel_id, channel_name, channel_type, is_system in channels
                    ],
                )
                await db.commit()

    async def remove_container_channel(self, guild_id: int, channel_id: int) -> None:
        async with self._write_lock:
            async with self.connect() as db:
                await db.execute("DELETE FROM container_channels WHERE guild_id = ? AND channel_id = ?", (str(guild_id), str(channel_id)))
                await db.commit()

    async def list_container_channels(self, guild_id: int, owner_id: int) -> list[aiosqlite.Row]:
        async with self.connect() as db:
            async with db.execute(
                "SELECT * FROM container_channels WHERE guild_id = ? AND owner_id = ? ORDER BY is_system DESC, id ASC",
                (str(guild_id), str(owner_id)),
            ) as cur:
                return await cur.fetchall()

    async def get_channel_record(self, guild_id: int, channel_id: int) -> aiosqlite.Row | None:
        async with self.connect() as db:
            async with db.execute(
                "SELECT * FROM container_channels WHERE guild_id = ? AND channel_id = ?",
                (str(guild_id), str(channel_id)),
            ) as cur:
                return await cur.fetchone()

    async def add_invite(self, guild_id: int, owner_id: int, invited_user_id: int) -> None:
        async with self._write_lock:
            async with self.connect() as db:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO container_invites (guild_id, owner_id, invited_user_id, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (str(guild_id), str(owner_id), str(invited_user_id), utcnow_iso()),
                )
                await db.commit()

    async def remove_invite(self, guild_id: int, owner_id: int, invited_user_id: int) -> None:
        async with self._write_lock:
            async with self.connect() as db:
                await db.execute(
                    "DELETE FROM container_invites WHERE guild_id = ? AND owner_id = ? AND invited_user_id = ?",
                    (str(guild_id), str(owner_id), str(invited_user_id)),
                )
                await db.commit()

    async def list_invites(self, guild_id: int, owner_id: int) -> list[aiosqlite.Row]:
        async with self.connect() as db:
            async with db.execute(
                "SELECT * FROM container_invites WHERE guild_id = ? AND owner_id = ? ORDER BY created_at ASC",
                (str(guild_id), str(owner_id)),
            ) as cur:
                return await cur.fetchall()
