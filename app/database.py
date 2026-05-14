import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.logger import logger


class Database:
    def __init__(self, db_path: str = "data/bot.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._pool: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self._pool = await aiosqlite.connect(self.db_path)
        self._pool.row_factory = aiosqlite.Row
        await self._create_tables()
        logger.info("Database connected")

    async def _create_tables(self):
        await self._pool.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                download_count INTEGER DEFAULT 0,
                total_downloads INTEGER DEFAULT 0,
                quality TEXT DEFAULT 'best',
                format_pref TEXT DEFAULT 'video',
                banned INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                url TEXT,
                platform TEXT,
                format TEXT,
                quality TEXT,
                file_size INTEGER,
                success INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS file_cache (
                url_hash TEXT PRIMARY KEY,
                platform TEXT,
                file_id TEXT,
                file_size INTEGER,
                file_name TEXT,
                mime_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS broadcast_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                message TEXT,
                total_users INTEGER,
                success_count INTEGER,
                fail_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await self._pool.commit()
        await self._migrate_schema()

    async def _migrate_schema(self):
        migrations = [
            "ALTER TABLE users ADD COLUMN video_resolution TEXT DEFAULT 'best'",
            "ALTER TABLE users ADD COLUMN audio_bitrate TEXT DEFAULT '192'",
            "ALTER TABLE downloads ADD COLUMN file_id TEXT",
        ]
        for sql in migrations:
            try:
                await self._pool.execute(sql)
                await self._pool.commit()
                logger.info(f"Schema migration: {sql[:60]}")
            except Exception:
                pass

    async def get_user(self, user_id: int) -> Optional[dict]:
        cursor = await self._pool.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def upsert_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ):
        existing = await self.get_user(user_id)
        now = datetime.utcnow().isoformat()
        if existing:
            await self._pool.execute(
                """UPDATE users SET username=?, first_name=?, last_name=?,
                   last_active=? WHERE user_id=?""",
                (username, first_name, last_name, now, user_id),
            )
        else:
            await self._pool.execute(
                """INSERT INTO users (user_id, username, first_name, last_name, joined_at, last_active)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, username, first_name, last_name, now, now),
            )
        await self._pool.commit()

    async def increment_downloads(self, user_id: int):
        await self._pool.execute(
            "UPDATE users SET download_count = download_count + 1, total_downloads = total_downloads + 1 WHERE user_id = ?",
            (user_id,),
        )
        await self._pool.commit()

    async def get_user_setting(self, user_id: int, key: str) -> Optional[str]:
        user = await self.get_user(user_id)
        if user:
            return user.get(key)
        return None

    async def update_user_setting(self, user_id: int, key: str, value: str):
        await self._pool.execute(
            f"UPDATE users SET {key} = ? WHERE user_id = ?", (value, user_id)
        )
        await self._pool.commit()

    async def log_download(
        self,
        user_id: int,
        url: str,
        platform: str,
        fmt: str,
        quality: str,
        file_size: int,
        file_id: Optional[str] = None,
        success: bool = True,
    ):
        await self._pool.execute(
            """INSERT INTO downloads (user_id, url, platform, format, quality, file_size, file_id, success)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, url, platform, fmt, quality, file_size, file_id, 1 if success else 0),
        )
        await self._pool.commit()

    async def get_total_users(self) -> int:
        cursor = await self._pool.execute("SELECT COUNT(*) as cnt FROM users")
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def get_all_users(self) -> list[dict]:
        cursor = await self._pool.execute("SELECT * FROM users WHERE banned = 0")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_total_downloads(self) -> int:
        cursor = await self._pool.execute(
            "SELECT COUNT(*) as cnt FROM downloads WHERE success = 1"
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def get_stats(self) -> dict:
        total_users = await self.get_total_users()
        total_downloads = await self.get_total_downloads()
        failed_row = await self._pool.execute(
            "SELECT COUNT(*) as cnt FROM downloads WHERE success = 0"
        )
        failed = (await failed_row.fetchone())["cnt"]

        size_cursor = await self._pool.execute(
            "SELECT COALESCE(SUM(file_size), 0) as total FROM downloads WHERE success = 1"
        )
        total_size = (await size_cursor.fetchone())["total"]

        return {
            "total_users": total_users,
            "total_downloads": total_downloads,
            "failed_downloads": failed,
            "total_size_bytes": total_size,
        }

    async def is_banned(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        if user:
            return bool(user.get("banned", 0))
        return False

    async def ban_user(self, user_id: int):
        await self._pool.execute(
            "UPDATE users SET banned = 1 WHERE user_id = ?", (user_id,)
        )
        await self._pool.commit()

    async def unban_user(self, user_id: int):
        await self._pool.execute(
            "UPDATE users SET banned = 0 WHERE user_id = ?", (user_id,)
        )
        await self._pool.commit()

    async def log_broadcast(self, admin_id: int, message: str, total: int, success: int, failed: int):
        await self._pool.execute(
            "INSERT INTO broadcast_log (admin_id, message, total_users, success_count, fail_count) VALUES (?, ?, ?, ?, ?)",
            (admin_id, message[:500], total, success, failed),
        )
        await self._pool.commit()

    async def get_cached_file(self, url_hash: str) -> Optional[dict]:
        cursor = await self._pool.execute(
            "SELECT * FROM file_cache WHERE url_hash = ?", (url_hash,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def set_cached_file(self, url_hash: str, platform: str, file_id: str, file_size: int, file_name: str, mime_type: str):
        await self._pool.execute(
            """INSERT OR REPLACE INTO file_cache (url_hash, platform, file_id, file_size, file_name, mime_type)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (url_hash, platform, file_id, file_size, file_name, mime_type),
        )
        await self._pool.commit()

    async def increment_cache_access(self, url_hash: str):
        await self._pool.execute(
            "UPDATE file_cache SET access_count = access_count + 1 WHERE url_hash = ?",
            (url_hash,),
        )
        await self._pool.commit()

    async def close(self):
        if self._pool:
            await self._pool.close()


db = Database()
