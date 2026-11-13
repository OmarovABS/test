from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_POSTGRES = DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
else:
    _configured_db_path = Path(os.getenv("DATABASE_PATH", "delivery.db"))
    DB_PATH = (_configured_db_path if _configured_db_path.is_absolute() else BASE_DIR / _configured_db_path).resolve()


class _PgCursor:
    """Thin wrapper adding sqlite-style lastrowid to a psycopg2 cursor."""

    def __init__(self, cursor: Any, returning_id: Any = None) -> None:
        self._cursor = cursor
        self._returning_id = returning_id

    @property
    def lastrowid(self) -> Any:
        return self._returning_id

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class _PgConnection:
    """SQLite-style execute() adapter over a psycopg2 connection."""

    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def cursor(self, *args: Any, **kwargs: Any) -> Any:
        return self._raw.cursor(*args, **kwargs)

    def execute(self, query: str, params: Any = ()) -> _PgCursor:
        stripped = query.lstrip()
        is_insert = stripped.upper().startswith("INSERT")
        has_returning = "RETURNING" in query.upper()
        sql = query.replace("?", "%s")
        if is_insert and not has_returning:
            sql = sql.rstrip().rstrip(";") + " RETURNING id"
        cursor = self._raw.cursor(cursor_factory=RealDictCursor)
        cursor.execute(sql, params or ())
        returning_id = None
        if is_insert and not has_returning:
            row = cursor.fetchone()
            returning_id = row["id"] if row else None
        return _PgCursor(cursor, returning_id)

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        self._raw.close()


@contextmanager
def connect_db() -> Generator[Any, None, None]:
    if USE_POSTGRES:
        raw = psycopg2.connect(DATABASE_URL)
        raw.autocommit = False
        connection = _PgConnection(raw)
        try:
            yield connection
            raw.commit()
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(DB_PATH, timeout=5.0)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=WAL;")
            connection.execute("PRAGMA busy_timeout=5000;")
            connection.execute("PRAGMA foreign_keys=ON;")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


SEED_PRODUCTS = (
    (1, "Донар классик", "Говядина, свежие овощи, лаваш", 32000, "Донар", "/images/donar-klassik.jpg"),
    (2, "Донар куриный", "Курица на гриле, соус, салат", 28000, "Донар", "/images/donar-kurinyy.jpg"),
    (3, "Донар XL", "Двойная порция мяса и сыр", 42000, "Донар", "/images/donar-xl.jpg"),
    (4, "Чизбургер", "Говяжья котлета, чеддер, томат", 35000, "Бургер", "/images/chizburger.jpg"),
    (5, "Биг бургер", "Две котлеты, лук, фирменный соус", 48000, "Бургер", "/images/big-burger.jpg"),
    (6, "Хот-дог классик", "Сосиска, горчица, булочка бриошь", 18000, "Хот-дог", "/images/hot-dog-klassik.jpg"),
    (7, "Хот-дог датский", "Хрустящий лук, огурчики", 22000, "Хот-дог", "/images/hot-dog-datskiy.jpg"),
    (8, "Лимонад", "Лимон, мята, лёд", 15000, "Напитки", "/images/limonad.jpg"),
    (9, "Айран", "Освежающий, домашний", 9000, "Напитки", "/images/ayran.jpg"),
    (10, "Пепперони", "Пепперони, моцарелла, томатный соус", 75000, "Пицца", "/images/pepperoni.jpg"),
    (11, "Маргарита", "Моцарелла, томаты, базилик", 62000, "Пицца", "/images/margarita.jpg"),
)


def init_db() -> None:
    with connect_db() as connection:
        if USE_POSTGRES:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    price INTEGER NOT NULL CHECK (price >= 0),
                    category TEXT NOT NULL,
                    image_url TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username TEXT NOT NULL DEFAULT '',
                    items_json TEXT NOT NULL,
                    total_price BIGINT NOT NULL CHECK (total_price >= 0),
                    address TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    comment TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP NOT NULL
                );
                """
            )
            # Migrate existing tables: Telegram user IDs and totals can exceed int32.
            cursor.execute("ALTER TABLE orders ALTER COLUMN user_id TYPE BIGINT;")
            cursor.execute("ALTER TABLE orders ALTER COLUMN total_price TYPE BIGINT;")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_active_category ON products(is_active, category);")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            
            cursor.execute("SELECT COUNT(*) FROM products")
            count = cursor.fetchone()["count"]
            if count == 0:
                cursor.executemany(
                    """INSERT INTO products
                       (id, name, description, price, category, image_url, is_active)
                       VALUES (%s, %s, %s, %s, %s, %s, 1)""",
                    SEED_PRODUCTS,
                )
        else:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    price INTEGER NOT NULL CHECK (price >= 0),
                    category TEXT NOT NULL,
                    image_url TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL DEFAULT '',
                    items_json TEXT NOT NULL,
                    total_price INTEGER NOT NULL CHECK (total_price >= 0),
                    address TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    comment TEXT NOT NULL DEFAULT '',
                    created_at DATETIME NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
                CREATE INDEX IF NOT EXISTS idx_products_active_category ON products(is_active, category);
                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            count = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            if count == 0:
                connection.executemany(
                    """INSERT INTO products
                       (id, name, description, price, category, image_url, is_active)
                       VALUES (?, ?, ?, ?, ?, ?, 1)""",
                    SEED_PRODUCTS,
                )


def row_to_dict(row: Any) -> dict[str, Any]:
    if USE_POSTGRES:
        result = dict(row)
    else:
        result = dict(row)
    if "is_active" in result:
        result["is_active"] = bool(result["is_active"])
    return result
