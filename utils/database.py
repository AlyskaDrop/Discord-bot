"""
Async SQLite database layer for the Weeping Ghosts Discord bot.

All tables are created on first run.  Public helpers follow the pattern:
  db.<noun>_<verb>(...)  →  returns a dict, list[dict], or plain value.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

import aiosqlite

import config

# ── helpers ───────────────────────────────────────────────────────────────────

def _row(row: aiosqlite.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def _rows(rows: list[aiosqlite.Row]) -> list[dict]:
    return [dict(r) for r in rows]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")


# ── initialisation ────────────────────────────────────────────────────────────

async def init() -> None:
    """Create all tables if they do not exist yet."""
    os.makedirs(os.path.dirname(config.DATABASE_PATH) or ".", exist_ok=True)
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.executescript("""
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id      TEXT UNIQUE NOT NULL,
                ingame_name     TEXT NOT NULL DEFAULT '',
                corp_role       TEXT NOT NULL DEFAULT 'pending',
                registered_at   TEXT NOT NULL,
                verified        INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS balance (
                user_id         INTEGER PRIMARY KEY REFERENCES users(id),
                isk             REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER REFERENCES users(id),
                amount          REAL NOT NULL,
                type            TEXT NOT NULL,
                description     TEXT NOT NULL DEFAULT '',
                created_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS points (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER REFERENCES users(id),
                pvp_points      INTEGER NOT NULL DEFAULT 0,
                pve_points      INTEGER NOT NULL DEFAULT 0,
                updated_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS kills (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id     INTEGER REFERENCES users(id),
                kill_data       TEXT NOT NULL,
                ship_destroyed  TEXT NOT NULL DEFAULT '',
                pilot_name      TEXT NOT NULL DEFAULT '',
                isk_value       REAL NOT NULL DEFAULT 0,
                posted_at       TEXT NOT NULL,
                approved        INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS compensations (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER REFERENCES users(id),
                ship_name       TEXT NOT NULL,
                ship_value      REAL NOT NULL DEFAULT 0,
                amount_paid     REAL NOT NULL DEFAULT 0,
                status          TEXT NOT NULL DEFAULT 'pending',
                requested_at    TEXT NOT NULL,
                resolved_at     TEXT
            );

            CREATE TABLE IF NOT EXISTS orders (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                title           TEXT NOT NULL,
                description     TEXT NOT NULL DEFAULT '',
                reward          REAL NOT NULL DEFAULT 0,
                status          TEXT NOT NULL DEFAULT 'open',
                created_by      INTEGER REFERENCES users(id),
                created_at      TEXT NOT NULL,
                closed_at       TEXT
            );

            CREATE TABLE IF NOT EXISTS shop_items (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                description     TEXT NOT NULL DEFAULT '',
                price           REAL NOT NULL DEFAULT 0,
                quantity        INTEGER NOT NULL DEFAULT 0,
                category        TEXT NOT NULL DEFAULT 'misc',
                added_by        INTEGER REFERENCES users(id),
                added_at        TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS auto_roles (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id         TEXT NOT NULL,
                role_name       TEXT NOT NULL,
                condition_type  TEXT NOT NULL,
                condition_value INTEGER NOT NULL DEFAULT 0
            );
        """)
        await db.commit()


# ── connection context ─────────────────────────────────────────────────────────

class _DB:
    """Thin wrapper so callers can do  `async with db.connect() as c:`"""

    async def __aenter__(self) -> aiosqlite.Connection:
        self._conn = await aiosqlite.connect(config.DATABASE_PATH)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    async def __aexit__(self, *_: Any) -> None:
        await self._conn.close()


connect = _DB


# ── users ─────────────────────────────────────────────────────────────────────

async def get_user(discord_id: str | int) -> dict | None:
    async with connect() as db:
        cur = await db.execute(
            "SELECT * FROM users WHERE discord_id = ?", (str(discord_id),)
        )
        return _row(await cur.fetchone())


async def create_user(discord_id: str | int, ingame_name: str = "") -> dict:
    async with connect() as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (discord_id, ingame_name, registered_at) VALUES (?, ?, ?)",
            (str(discord_id), ingame_name, _now()),
        )
        await db.commit()
        cur = await db.execute(
            "SELECT * FROM users WHERE discord_id = ?", (str(discord_id),)
        )
        row = _row(await cur.fetchone())
        # ensure balance row exists
        if row:
            await db.execute(
                "INSERT OR IGNORE INTO balance (user_id, isk) VALUES (?, 0)", (row["id"],)
            )
            await db.execute(
                "INSERT OR IGNORE INTO points (user_id, pvp_points, pve_points, updated_at) VALUES (?, 0, 0, ?)",
                (row["id"], _now()),
            )
            await db.commit()
        return row  # type: ignore[return-value]


_ALLOWED_USER_FIELDS = frozenset(
    {"ingame_name", "corp_role", "registered_at", "verified"}
)


async def update_user(discord_id: str | int, **fields: Any) -> None:
    if not fields:
        return
    invalid = set(fields) - _ALLOWED_USER_FIELDS
    if invalid:
        raise ValueError(f"Invalid user field(s): {invalid}")
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [str(discord_id)]
    async with connect() as db:
        await db.execute(
            f"UPDATE users SET {set_clause} WHERE discord_id = ?", values
        )
        await db.commit()


async def get_all_users() -> list[dict]:
    async with connect() as db:
        cur = await db.execute("SELECT * FROM users ORDER BY registered_at DESC")
        return _rows(await cur.fetchall())


# ── balance ───────────────────────────────────────────────────────────────────

async def get_balance(discord_id: str | int) -> float:
    user = await get_user(discord_id)
    if not user:
        return 0.0
    async with connect() as db:
        cur = await db.execute(
            "SELECT isk FROM balance WHERE user_id = ?", (user["id"],)
        )
        row = await cur.fetchone()
        return float(row["isk"]) if row else 0.0


async def modify_balance(
    discord_id: str | int,
    amount: float,
    tx_type: str = "manual",
    description: str = "",
) -> float:
    user = await get_user(discord_id)
    if not user:
        user = await create_user(discord_id)
    async with connect() as db:
        await db.execute(
            "UPDATE balance SET isk = MAX(0, isk + ?) WHERE user_id = ?",
            (amount, user["id"]),
        )
        await db.execute(
            "INSERT INTO transactions (user_id, amount, type, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (user["id"], amount, tx_type, description, _now()),
        )
        await db.commit()
        cur = await db.execute(
            "SELECT isk FROM balance WHERE user_id = ?", (user["id"],)
        )
        row = await cur.fetchone()
        return float(row["isk"]) if row else 0.0


async def get_balance_leaderboard(limit: int = 10) -> list[dict]:
    async with connect() as db:
        cur = await db.execute(
            """SELECT u.discord_id, u.ingame_name, b.isk
               FROM balance b JOIN users u ON b.user_id = u.id
               ORDER BY b.isk DESC LIMIT ?""",
            (limit,),
        )
        return _rows(await cur.fetchall())


async def get_transactions(discord_id: str | int, limit: int = 10) -> list[dict]:
    user = await get_user(discord_id)
    if not user:
        return []
    async with connect() as db:
        cur = await db.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user["id"], limit),
        )
        return _rows(await cur.fetchall())


# ── points ────────────────────────────────────────────────────────────────────

async def get_points(discord_id: str | int) -> dict:
    user = await get_user(discord_id)
    if not user:
        return {"pvp_points": 0, "pve_points": 0}
    async with connect() as db:
        cur = await db.execute(
            "SELECT pvp_points, pve_points FROM points WHERE user_id = ?",
            (user["id"],),
        )
        row = await cur.fetchone()
        if not row:
            return {"pvp_points": 0, "pve_points": 0}
        return dict(row)


async def add_points(
    discord_id: str | int, pvp: int = 0, pve: int = 0
) -> dict:
    user = await get_user(discord_id)
    if not user:
        user = await create_user(discord_id)
    async with connect() as db:
        await db.execute(
            """UPDATE points
               SET pvp_points = pvp_points + ?,
                   pve_points = pve_points + ?,
                   updated_at = ?
               WHERE user_id = ?""",
            (pvp, pve, _now(), user["id"]),
        )
        await db.commit()
    return await get_points(discord_id)


async def get_points_leaderboard(limit: int = 10) -> list[dict]:
    async with connect() as db:
        cur = await db.execute(
            """SELECT u.discord_id, u.ingame_name,
                      p.pvp_points, p.pve_points,
                      (p.pvp_points + p.pve_points) AS total_points
               FROM points p JOIN users u ON p.user_id = u.id
               ORDER BY total_points DESC LIMIT ?""",
            (limit,),
        )
        return _rows(await cur.fetchall())


# ── kills ─────────────────────────────────────────────────────────────────────

async def add_kill(
    reporter_discord_id: str | int,
    kill_data: str,
    ship_destroyed: str = "",
    pilot_name: str = "",
    isk_value: float = 0.0,
) -> int:
    user = await get_user(reporter_discord_id)
    if not user:
        user = await create_user(reporter_discord_id)
    async with connect() as db:
        cur = await db.execute(
            """INSERT INTO kills
               (reporter_id, kill_data, ship_destroyed, pilot_name, isk_value, posted_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user["id"], kill_data, ship_destroyed, pilot_name, isk_value, _now()),
        )
        await db.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def approve_kill(kill_id: int) -> bool:
    async with connect() as db:
        await db.execute(
            "UPDATE kills SET approved = 1 WHERE id = ?", (kill_id,)
        )
        await db.commit()
        return True


async def get_kills(limit: int = 20, approved_only: bool = True) -> list[dict]:
    async with connect() as db:
        if approved_only:
            cur = await db.execute(
                """SELECT k.*, u.discord_id, u.ingame_name
                   FROM kills k JOIN users u ON k.reporter_id = u.id
                   WHERE k.approved = 1
                   ORDER BY k.posted_at DESC LIMIT ?""",
                (limit,),
            )
        else:
            cur = await db.execute(
                """SELECT k.*, u.discord_id, u.ingame_name
                   FROM kills k JOIN users u ON k.reporter_id = u.id
                   ORDER BY k.posted_at DESC LIMIT ?""",
                (limit,),
            )
        return _rows(await cur.fetchall())


# ── compensations ─────────────────────────────────────────────────────────────

async def request_compensation(
    discord_id: str | int, ship_name: str, ship_value: float
) -> int:
    user = await get_user(discord_id)
    if not user:
        user = await create_user(discord_id)
    amount_paid = ship_value * config.COMPENSATION_BASE_PERCENT
    async with connect() as db:
        cur = await db.execute(
            """INSERT INTO compensations
               (user_id, ship_name, ship_value, amount_paid, requested_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user["id"], ship_name, ship_value, amount_paid, _now()),
        )
        await db.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def resolve_compensation(comp_id: int, approve: bool) -> None:
    status = "approved" if approve else "rejected"
    async with connect() as db:
        await db.execute(
            "UPDATE compensations SET status = ?, resolved_at = ? WHERE id = ?",
            (status, _now(), comp_id),
        )
        await db.commit()


async def get_pending_compensations() -> list[dict]:
    async with connect() as db:
        cur = await db.execute(
            """SELECT c.*, u.discord_id, u.ingame_name
               FROM compensations c JOIN users u ON c.user_id = u.id
               WHERE c.status = 'pending'
               ORDER BY c.requested_at""",
        )
        return _rows(await cur.fetchall())


async def get_user_compensations(discord_id: str | int, limit: int = 10) -> list[dict]:
    """Return the most recent compensation requests for a specific user."""
    user = await get_user(discord_id)
    if not user:
        return []
    async with connect() as db:
        cur = await db.execute(
            "SELECT * FROM compensations WHERE user_id = ? ORDER BY requested_at DESC LIMIT ?",
            (user["id"], limit),
        )
        return _rows(await cur.fetchall())


# ── orders ────────────────────────────────────────────────────────────────────

async def create_order(
    discord_id: str | int, title: str, description: str, reward: float
) -> int:
    user = await get_user(discord_id)
    if not user:
        user = await create_user(discord_id)
    async with connect() as db:
        cur = await db.execute(
            """INSERT INTO orders (title, description, reward, created_by, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (title, description, reward, user["id"], _now()),
        )
        await db.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def get_orders(status: str = "open") -> list[dict]:
    async with connect() as db:
        cur = await db.execute(
            """SELECT o.*, u.discord_id, u.ingame_name
               FROM orders o JOIN users u ON o.created_by = u.id
               WHERE o.status = ?
               ORDER BY o.created_at DESC""",
            (status,),
        )
        return _rows(await cur.fetchall())


async def close_order(order_id: int) -> None:
    async with connect() as db:
        await db.execute(
            "UPDATE orders SET status = 'closed', closed_at = ? WHERE id = ?",
            (_now(), order_id),
        )
        await db.commit()


# ── shop ──────────────────────────────────────────────────────────────────────

async def add_shop_item(
    discord_id: str | int,
    name: str,
    description: str,
    price: float,
    quantity: int,
    category: str,
) -> int:
    user = await get_user(discord_id)
    if not user:
        user = await create_user(discord_id)
    async with connect() as db:
        cur = await db.execute(
            """INSERT INTO shop_items
               (name, description, price, quantity, category, added_by, added_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, description, price, quantity, category, user["id"], _now()),
        )
        await db.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def get_shop_items(category: str | None = None) -> list[dict]:
    async with connect() as db:
        if category:
            cur = await db.execute(
                "SELECT * FROM shop_items WHERE category = ? AND quantity > 0 ORDER BY name",
                (category,),
            )
        else:
            cur = await db.execute(
                "SELECT * FROM shop_items WHERE quantity > 0 ORDER BY category, name"
            )
        return _rows(await cur.fetchall())


async def remove_shop_item(item_id: int) -> None:
    async with connect() as db:
        await db.execute("DELETE FROM shop_items WHERE id = ?", (item_id,))
        await db.commit()


# ── auto_roles ────────────────────────────────────────────────────────────────

async def get_auto_roles() -> list[dict]:
    async with connect() as db:
        cur = await db.execute("SELECT * FROM auto_roles ORDER BY condition_value")
        return _rows(await cur.fetchall())


async def add_auto_role(
    role_id: str, role_name: str, condition_type: str, condition_value: int
) -> None:
    async with connect() as db:
        await db.execute(
            """INSERT INTO auto_roles (role_id, role_name, condition_type, condition_value)
               VALUES (?, ?, ?, ?)""",
            (role_id, role_name, condition_type, condition_value),
        )
        await db.commit()


async def remove_auto_role(role_id: str) -> None:
    async with connect() as db:
        await db.execute("DELETE FROM auto_roles WHERE role_id = ?", (role_id,))
        await db.commit()
