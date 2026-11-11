from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

BASE_DIR = Path(__file__).resolve().parent.parent
_configured_db_path = Path(os.getenv("DATABASE_PATH", "delivery.db"))
DB_PATH = (_configured_db_path if _configured_db_path.is_absolute() else BASE_DIR / _configured_db_path).resolve()

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


@contextmanager
def connect_db() -> Generator[sqlite3.Connection, None, None]:
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


def init_db() -> None:
    with connect_db() as connection:
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


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    if "is_active" in result:
        result["is_active"] = bool(result["is_active"])
    return result
