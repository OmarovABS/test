from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from html import escape
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, AsyncGenerator
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env", override=True)

from .auth import verify_init_data
from .database import BASE_DIR, connect_db, init_db, row_to_dict

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", os.getenv("ADMIN_ID", "")).strip()
ADMIN_IDS = {
    value.strip()
    for value in os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", "")).split(",")
    if value.strip()
}
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() in {"1", "true", "yes", "on"}
RESTAURANT_NAME = os.getenv("RESTAURANT_NAME", "Premium Food").strip() or "Premium Food"
STATIC_DIR = BASE_DIR
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    yield


app = FastAPI(title="Premium Food Delivery API", version="1.0.0", lifespan=lifespan)


class OrderItem(BaseModel):
    product_id: int = Field(gt=0)
    qty: int = Field(ge=1, le=99)


class OrderCreate(BaseModel):
    items: list[OrderItem] = Field(min_length=1, max_length=50)
    address: str = Field(default="", max_length=500)
    phone: str = Field(default="", max_length=40)
    comment: str = Field(default="", max_length=1000)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    price: int | None = Field(default=None, ge=0, le=100_000_000)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    image_url: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None


def _get_telegram_user(init_data: str | None, request: Request) -> dict[str, Any] | None:
    if init_data:
        return verify_init_data(init_data, BOT_TOKEN) if BOT_TOKEN else None
    if DEBUG_MODE:
        return {"id": 0, "first_name": "Debug User", "username": "debug"}
    return None


def current_user(
    request: Request,
    x_telegram_init_data: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    user = _get_telegram_user(x_telegram_init_data, request)
    if user is None:
        raise HTTPException(status_code=401, detail="Откройте приложение через Telegram.")
    return user


def require_admin(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if str(user.get("id")) not in ADMIN_IDS:
        # Local-only browser testing is isolated from non-loopback clients in current_user.
        if not (DEBUG_MODE and user.get("id") == 0):
            raise HTTPException(status_code=403, detail="Недостаточно прав.")
    return user


def product_payload(row: sqlite3.Row) -> dict[str, Any]:
    return row_to_dict(row)


def public_image_url(image_url: str) -> str:
    if image_url and not image_url.startswith(("http://", "https://", "/")):
        return "/" + image_url.lstrip("./")
    return image_url


def save_product(
    *, product_id: int | None, name: str, description: str, price: int,
    category: str, image_url: str, is_active: bool,
) -> dict[str, Any]:
    name, category = name.strip(), category.strip()
    if not name or not category:
        raise HTTPException(status_code=422, detail="Название и категория обязательны.")
    with connect_db() as connection:
        if product_id is None:
            cursor = connection.execute(
                """INSERT INTO products(name, description, price, category, image_url, is_active)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, description.strip(), price, category, image_url.strip(), int(is_active)),
            )
            product_id = cursor.lastrowid
        else:
            cursor = connection.execute(
                """UPDATE products SET name=?, description=?, price=?, category=?, image_url=?, is_active=?
                   WHERE id=?""",
                (name, description.strip(), price, category, image_url.strip(), int(is_active), product_id),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Блюдо не найдено.")
        row = connection.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        result = product_payload(row)
        result["image_url"] = public_image_url(result["image_url"])
        return result


async def persist_upload(image: UploadFile | None) -> str | None:
    if image is None or not image.filename:
        return None
    suffix = ALLOWED_IMAGE_TYPES.get(image.content_type or "")
    if suffix is None:
        raise HTTPException(status_code=415, detail="Поддерживаются JPEG, PNG, WEBP и GIF.")
    data = await image.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Размер изображения не должен превышать 8 МБ.")
    filename = f"{uuid.uuid4().hex}{suffix}"
    (UPLOAD_DIR / filename).write_bytes(data)
    return f"/static/uploads/{filename}"


def validate_remote_image(url: str) -> str:
    url = url.strip()
    if url and not re.match(r"^https?://", url, re.IGNORECASE):
        raise HTTPException(status_code=422, detail="Ссылка на изображение должна начинаться с http:// или https://.")
    return url


@app.get("/api/me")
def get_me(request: Request, x_telegram_init_data: Annotated[str | None, Header()] = None) -> dict[str, bool]:
    user = _get_telegram_user(x_telegram_init_data, request)
    if user is None:
        # Keep normal browser storefront usable while withholding admin access.
        return {"is_admin": False}
    return {"is_admin": str(user.get("id")) in ADMIN_IDS or (DEBUG_MODE and user.get("id") == 0)}


@app.get("/api/menu")
def get_menu() -> dict[str, list[dict[str, Any]]]:
    with connect_db() as connection:
        rows = connection.execute(
            "SELECT id, name, description, price, category, image_url FROM products WHERE is_active=1 ORDER BY category, id"
        ).fetchall()
    products = [product_payload(row) for row in rows]
    for product in products:
        product["image_url"] = public_image_url(product["image_url"])
    return {"products": products}


@app.post("/api/orders", status_code=201)
async def create_order(order: OrderCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    merged: dict[int, int] = {}
    for item in order.items:
        merged[item.product_id] = merged.get(item.product_id, 0) + item.qty
    if any(quantity > 99 for quantity in merged.values()):
        raise HTTPException(status_code=422, detail="Максимум 99 единиц одного блюда.")

    with connect_db() as connection:
        placeholders = ",".join("?" for _ in merged)
        rows = connection.execute(
            f"SELECT id, name, price FROM products WHERE is_active=1 AND id IN ({placeholders})",
            list(merged),
        ).fetchall()
        by_id = {row["id"]: row for row in rows}
        if len(by_id) != len(merged):
            raise HTTPException(status_code=409, detail="Некоторые блюда больше недоступны. Обновите меню.")
        items = [
            {"product_id": product_id, "name": by_id[product_id]["name"],
             "price": by_id[product_id]["price"], "qty": quantity}
            for product_id, quantity in merged.items()
        ]
        subtotal = sum(item["price"] * item["qty"] for item in items)
        total = subtotal + (10000 if items else 0)
        user_id = int(user["id"])
        username = str(user.get("username") or "")
        created_at = datetime.now(ZoneInfo("Asia/Tashkent")).isoformat(timespec="seconds")
        cursor = connection.execute(
            """INSERT INTO orders(user_id, username, items_json, total_price, address, phone, comment, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, json.dumps(items, ensure_ascii=False), total, order.address.strip(),
             order.phone.strip(), order.comment.strip(), created_at),
        )
        order_id = cursor.lastrowid

    if BOT_TOKEN and ADMIN_CHAT_ID:
        name = " ".join(str(user.get(key, "")) for key in ("first_name", "last_name")).strip() or "Клиент"
        lines = [f"• {escape(item['name'])} ×{item['qty']} — {item['price'] * item['qty']:,} сум".replace(",", " ") for item in items]
        message = (
            f"🆕 <b>Новый заказ #{order_id}</b>\n\n"
            f"👤 {escape(name)} (@{escape(username)})\n🆔 <code>{user_id}</code>\n\n"
            + "\n".join(lines)
            + f"\n\n🛵 Доставка: 10 000 сум\n💰 <b>Итого: {total:,} сум</b>".replace(",", " ")
            + f"\n📍 Адрес: {escape(order.address.strip() or 'Не указан')}"
            + f"\n📞 Телефон: {escape(order.phone.strip() or 'Не указан')}"
            + f"\n💬 Комментарий: {escape(order.comment.strip() or '—')}"
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": ADMIN_CHAT_ID, "text": message, "parse_mode": "HTML"},
                )
                response.raise_for_status()
                if not response.json().get("ok"):
                    raise httpx.HTTPError("Telegram API rejected the message")
        except (httpx.HTTPError, ValueError) as error:
            # Order is already persisted; return its ID to prevent accidental duplicate submissions.
            print(f"Telegram notification failed for order {order_id}: {error}")
            return {"ok": True, "order_id": order_id, "notification_sent": False}
    else:
        print(f"Order {order_id} saved; Telegram notification is not configured.")
    return {"ok": True, "order_id": order_id, "notification_sent": bool(BOT_TOKEN and ADMIN_CHAT_ID)}


@app.get("/api/admin/products")
def admin_products(_: dict[str, Any] = Depends(require_admin)) -> dict[str, list[dict[str, Any]]]:
    with connect_db() as connection:
        rows = connection.execute("SELECT * FROM products ORDER BY category, name").fetchall()
    products = [product_payload(row) for row in rows]
    for product in products:
        product["image_url"] = public_image_url(product["image_url"])
    return {"products": products}


@app.post("/api/admin/products", status_code=201)
async def create_product(
    name: Annotated[str, Form()],
    price: Annotated[int, Form(ge=0, le=100_000_000)],
    category: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    image_url: Annotated[str, Form()] = "",
    is_active: Annotated[bool, Form()] = True,
    image: Annotated[UploadFile | None, File()] = None,
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    uploaded = await persist_upload(image)
    chosen_image = uploaded or validate_remote_image(image_url)
    return {"product": save_product(product_id=None, name=name, description=description, price=price,
                                     category=category, image_url=chosen_image, is_active=is_active)}


@app.put("/api/admin/products/{product_id}")
async def update_product(
    product_id: int,
    request: Request,
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        values = {key: value for key, value in form.items() if key != "image"}
        image = form.get("image")
        with connect_db() as connection:
            old = connection.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if old is None:
            raise HTTPException(status_code=404, detail="Блюдо не найдено.")
        data: dict[str, Any] = row_to_dict(old)
        data.update(values)
        if "is_active" in values:
            data["is_active"] = str(values["is_active"]).lower() in {"true", "1", "on", "yes"}
        if "price" in values:
            data["price"] = int(values["price"])
        uploaded = await persist_upload(image if hasattr(image, "read") else None)
        if uploaded:
            data["image_url"] = uploaded
        elif "image_url" in values:
            data["image_url"] = validate_remote_image(str(values["image_url"]))
    else:
        try:
            values = await request.json()
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Некорректный JSON.") from error
        patch = ProductUpdate.model_validate(values)
        with connect_db() as connection:
            old = connection.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if old is None:
            raise HTTPException(status_code=404, detail="Блюдо не найдено.")
        data = row_to_dict(old)
        data.update(patch.model_dump(exclude_unset=True))
        if "image_url" in patch.model_fields_set:
            data["image_url"] = validate_remote_image(data["image_url"])
    return {"product": save_product(product_id=product_id, name=str(data["name"]),
                                     description=str(data["description"]), price=int(data["price"]),
                                     category=str(data["category"]), image_url=str(data["image_url"]),
                                     is_active=bool(data["is_active"]))}


@app.delete("/api/admin/products/{product_id}", status_code=204)
def delete_product(product_id: int, _: dict[str, Any] = Depends(require_admin)) -> None:
    with connect_db() as connection:
        row = connection.execute("SELECT image_url FROM products WHERE id=?", (product_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Блюдо не найдено.")
        connection.execute("DELETE FROM products WHERE id=?", (product_id,))
    image_url = row["image_url"]
    if image_url.startswith("/static/uploads/"):
        path = (BASE_DIR / image_url.lstrip("/")).resolve()
        if path.parent == UPLOAD_DIR.resolve() and path.is_file():
            path.unlink(missing_ok=True)


@app.get("/api/admin/orders")
def admin_orders(_: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    today = datetime.now(ZoneInfo("Asia/Tashkent")).date().isoformat()
    with connect_db() as connection:
        orders = connection.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 50").fetchall()
        stats = connection.execute(
            "SELECT COUNT(*) AS count, COALESCE(SUM(total_price), 0) AS revenue FROM orders WHERE substr(created_at, 1, 10)=?",
            (today,),
        ).fetchone()
    result = []
    for row in orders:
        item = row_to_dict(row)
        try:
            item["items"] = json.loads(item.pop("items_json"))
        except (TypeError, json.JSONDecodeError):
            item["items"] = []
        result.append(item)
    return {"orders": result, "today": {"count": stats["count"], "revenue": stats["revenue"]}}


# Serve uploads separately, then the existing storefront files without copying or rewriting them.
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/images", StaticFiles(directory=BASE_DIR / "images"), name="images")


@app.get("/", include_in_schema=False)
def storefront() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# Existing CSS and JS references are relative to the project root.
app.mount("/assets", StaticFiles(directory=BASE_DIR), name="project-assets")


@app.get("/{asset_path:path}", include_in_schema=False)
def frontend_assets(asset_path: str) -> FileResponse:
    candidate = (BASE_DIR / asset_path).resolve()
    if not candidate.is_relative_to(BASE_DIR.resolve()) or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден.")
    return FileResponse(candidate)
