import json
import os
import sys
import time
import urllib.error
import urllib.request
from html import escape
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent


def load_env(path):
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env(BASE_DIR / ".env")

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = os.environ.get("ADMIN_ID", "").strip()
MINI_APP_URL = os.environ.get("MINI_APP_URL", "").strip()
NAME = os.environ.get("RESTAURANT_NAME", "Premium Food").strip() or "Premium Food"
SUPPORT = os.environ.get("SUPPORT_USERNAME", "").strip().lstrip("@")

PRODUCTS = {
    1: ("Донар классик", 32000),
    2: ("Донар куриный", 28000),
    3: ("Донар XL", 42000),
    4: ("Чизбургер", 35000),
    5: ("Биг бургер", 48000),
    6: ("Хот-дог классик", 18000),
    7: ("Хот-дог датский", 22000),
    8: ("Лимонад", 15000),
    9: ("Айран", 9000),
    10: ("Пепперони", 75000),
    11: ("Маргарита", 62000),
}
DELIVERY_PRICE = 10000

if not TOKEN:
    raise SystemExit("Не найден BOT_TOKEN. Укажите его в файле .env рядом с bot.py.")

API = f"https://api.telegram.org/bot{TOKEN}/"
seen_users = set()


def call(method, **params):
    payload = json.dumps(params, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        API + method,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        print(f"[{method}] HTTP {error.code}: {body}")
        return None
    except Exception as error:
        print(f"[{method}] {error}")
        return None
    if not data.get("ok"):
        print(f"[{method}] {data}")
        return None
    return data.get("result")


def greeting(name):
    return (
        f"Здравствуйте, <b>{escape(name)}</b>! 👋\n\n"
        f"Добро пожаловать в <b>{escape(NAME)}</b> 🍔\n"
        "Готовим вкусно и доставляем быстро по Ташкенту.\n\n"
        "<blockquote>"
        "🔥 Свежие бургеры, донары и пицца\n"
        "🛵 Доставка от 30 минут\n"
        "💳 Оплата наличными или картой"
        "</blockquote>\n\n"
        "Выберите действие ниже 👇"
    )


def main_keyboard():
    if MINI_APP_URL.startswith("https://"):
        return {
            "keyboard": [[{"text": "🍔 Открыть меню", "web_app": {"url": MINI_APP_URL}}]],
            "resize_keyboard": True,
        }
    return {"keyboard": [[{"text": "🍔 Меню"}]], "resize_keyboard": True}


def location_keyboard():
    keyboard = []
    if MINI_APP_URL.startswith("https://"):
        keyboard.append([{"text": "🍔 Открыть меню", "web_app": {"url": MINI_APP_URL}}])
    return {
        "keyboard": keyboard + [[{"text": "📍 Отправить геолокацию", "request_location": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    }


def back_keyboard():
    return {"inline_keyboard": [[{"text": "‹ Назад", "callback_data": "start"}]]}


def screen_text(key, user_name="друг"):
    if key == "menu":
        return (
            "🍔 <b>Меню</b>\n\n"
            "🌯 Донары · от 28 000 сум\n"
            "🍔 Бургеры · от 35 000 сум\n"
            "🌭 Хот-доги · от 18 000 сум\n"
            "🍕 Пицца · от 62 000 сум\n"
            "🥤 Напитки · от 9 000 сум\n\n"
            "Всё свежее, готовим после заказа."
        )
    if key == "cart":
        return (
            "🛒 <b>Корзина</b>\n\n"
            "Пока пусто. Добавьте блюда из меню — "
            "и мы соберём заказ за пару минут."
        )
    if key == "orders":
        return (
            "📦 <b>Мои заказы</b>\n\n"
            "После оформления заказ отправляется администратору.\n"
            "История заказов и статусы доставки пока не сохраняются."
        )
    if key == "support":
        lines = [
            "💬 <b>Служба поддержки</b>\n",
            "Мы на связи каждый день с 10:00 до 23:00.",
        ]
        if SUPPORT:
            lines.append(f'\nНаписать: <a href="https://t.me/{SUPPORT}">@{SUPPORT}</a>')
        else:
            lines.append("\nОтветим прямо здесь — просто напишите сообщение.")
        return "\n".join(lines)
    if key == "about":
        return (
            f"ℹ️ <b>О {escape(NAME)}</b>\n\n"
            "Готовим любимую еду из свежих продуктов и доставляем по Ташкенту.\n\n"
            "🕒 Работаем с 10:00 до 23:00\n"
            "🛵 Доставка от 30 минут\n"
            "💳 Наличные и карта\n\n"
            "Спасибо, что выбираете нас ❤️"
        )
    return greeting(user_name)


def notify_admin(user):
    if not ADMIN_ID:
        return
    username = f"@{user['username']}" if user.get("username") else "—"
    full = " ".join(
        part for part in (user.get("first_name"), user.get("last_name")) if part
    ).strip()
    text = (
        "🆕 <b>Новый пользователь</b>\n\n"
        f"👤 {escape(full or 'Без имени')}\n"
        f"🔗 {escape(username)}\n"
        f"🆔 <code>{user.get('id')}</code>"
    )
    try:
        call("sendMessage", chat_id=int(ADMIN_ID), text=text, parse_mode="HTML")
    except ValueError:
        print("ADMIN_ID должен быть числом.")


def handle_location(message):
    chat_id = message["chat"]["id"]
    user = message.get("from", {}) or {}
    loc = message.get("location") or {}
    lat, lon = loc.get("latitude"), loc.get("longitude")
    if lat is None or lon is None:
        return
    name = user.get("first_name") or "друг"
    maps_url = f"https://maps.google.com/?q={lat},{lon}"
    text = (
        f"📍 <b>Геолокация получена</b>\n\n"
        f"Широта: <code>{lat}</code>\n"
        f"Долгота: <code>{lon}</code>\n\n"
        f'<a href="{maps_url}">Открыть на карте</a>'
    )
    call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML", disable_web_page_preview=True)
    if ADMIN_ID and str(user.get("id")) != ADMIN_ID:
        uname = f"@{user['username']}" if user.get("username") else "—"
        admin_text = (
            "📍 <b>Клиент поделился геолокацией</b>\n\n"
            f"👤 {escape(name)} ({escape(uname)})\n"
            f"🆔 <code>{user.get('id')}</code>\n"
            f"📌 <code>{lat}, {lon}</code>\n"
            f'<a href="{maps_url}">Карта</a>'
        )
        try:
            call("sendMessage", chat_id=int(ADMIN_ID), text=admin_text, parse_mode="HTML", disable_web_page_preview=True)
        except ValueError:
            pass


def handle_web_app_order(message):
    web_app_data = message.get("web_app_data") or {}
    user = message.get("from", {}) or {}
    chat_id = message.get("chat", {}).get("id")
    raw_data = web_app_data.get("data", "")
    if not isinstance(raw_data, str) or len(raw_data) > 4096:
        call("sendMessage", chat_id=chat_id, text="Данные заказа слишком большие. Уменьшите корзину и попробуйте снова.")
        return
    try:
        payload = json.loads(raw_data)
    except (TypeError, json.JSONDecodeError):
        call("sendMessage", chat_id=chat_id, text="Не удалось прочитать заказ. Пожалуйста, попробуйте ещё раз.")
        return

    requested_items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(requested_items, list) or not requested_items or len(requested_items) > len(PRODUCTS):
        call("sendMessage", chat_id=chat_id, text="Корзина пуста или содержит некорректные товары.")
        return

    items = []
    total = 0
    seen = set()
    for requested in requested_items:
        if not isinstance(requested, dict):
            continue
        try:
            product_id = int(requested.get("product_id"))
            qty = int(requested.get("qty"))
        except (TypeError, ValueError):
            continue
        if product_id not in PRODUCTS or not 1 <= qty <= 99 or product_id in seen:
            continue
        seen.add(product_id)
        product_name, price = PRODUCTS[product_id]
        items.append((product_name, price, qty))
        total += price * qty

    if not items:
        call("sendMessage", chat_id=chat_id, text="В заказе нет доступных товаров. Обновите меню и попробуйте снова.")
        return

    address = payload.get("address", "")
    if not isinstance(address, str):
        address = ""
    address = address.strip()[:300] or "Не указан"
    customer_name = " ".join(
        part for part in (user.get("first_name"), user.get("last_name")) if part
    ).strip() or "Без имени"
    username = f"@{user['username']}" if user.get("username") else "—"
    order_ref = f"{user.get('id', '—')}-{message.get('message_id', '—')}"
    item_lines = "\n".join(
        f"• {html.escape(name)} ×{qty} — {fmt_sum(price * qty)} сум"
        for name, price, qty in items
    )
    total += DELIVERY_PRICE
    admin_text = (
        "🆕 <b>Новый заказ из Mini App</b>\n\n"
        f"🧾 Заказ #{order_ref}\n"
        f"👤 {html.escape(customer_name)} ({html.escape(username)})\n"
        f"🆔 <code>{user.get('id', '—')}</code>\n\n"
        f"{item_lines}\n\n"
        f"🛵 Доставка: {fmt_sum(DELIVERY_PRICE)} сум\n"
        f"💰 Итого: <b>{fmt_sum(total)} сум</b>\n"
        f"📍 Адрес: {html.escape(address)}"
    )

    if not ADMIN_ID:
        call("sendMessage", chat_id=chat_id, text="Заказ не отправлен: не настроен Telegram ID администратора.")
        return
    try:
        admin_chat_id = int(ADMIN_ID)
    except ValueError:
        call("sendMessage", chat_id=chat_id, text="Заказ не отправлен: неверно настроен администратор.")
        return
    if not call("sendMessage", chat_id=admin_chat_id, text=admin_text, parse_mode="HTML"):
        call("sendMessage", chat_id=chat_id, text="Не удалось передать заказ администратору. Попробуйте позже.")
        return
    call("sendMessage", chat_id=chat_id, text="✅ Заказ отправлен! Администратор скоро свяжется с вами.")


def handle_message(message):
    chat_id = message["chat"]["id"]
    user = message.get("from", {}) or {}
    text = (message.get("text") or "").strip()
    name = user.get("first_name") or "друг"

    if message.get("web_app_data"):
        handle_web_app_order(message)
        return

    if "location" in message:
        handle_location(message)
        return

    if text.startswith("/start"):
        call(
            "sendMessage",
            chat_id=chat_id,
            text=greeting(name),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )
        call("sendMessage", chat_id=chat_id, text="📍 Поделитесь геолокацией для точной доставки:", reply_markup=location_keyboard())
        uid = user.get("id")
        if str(uid) != ADMIN_ID and uid not in seen_users:
            seen_users.add(uid)
            notify_admin(user)
        return

    commands = {
        "/menu": "menu",
        "/cart": "cart",
        "/orders": "orders",
        "/support": "support",
        "/help": "about",
    }
    command = text.split()[0].lower() if text else ""
    if command in commands:
        key = commands[command]
        call(
            "sendMessage",
            chat_id=chat_id,
            text=screen_text(key, name),
            parse_mode="HTML",
            reply_markup=back_keyboard(),
        )
        return

    call(
        "sendMessage",
        chat_id=chat_id,
        text="Я рядом 👋\nВыберите пункт в меню ниже или нажмите /start.",
        reply_markup=main_keyboard(),
    )


def handle_callback(callback):
    data = callback.get("data", "")
    user = callback.get("from", {}) or {}
    message = callback.get("message") or {}
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")

    call("answerCallbackQuery", callback_query_id=callback["id"])

    if data == "start":
        text = greeting(user.get("first_name") or "друг")
        markup = main_keyboard()
    else:
        text = screen_text(data, user.get("first_name") or "друг")
        markup = back_keyboard()

    if chat_id and message_id:
        call(
            "editMessageText",
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=markup,
        )


def setup_bot():
    call(
        "setMyCommands",
        commands=[
            {"command": "start", "description": "Приветствие"},
            {"command": "menu", "description": "Меню"},
            {"command": "cart", "description": "Корзина"},
            {"command": "orders", "description": "Мои заказы"},
            {"command": "support", "description": "Поддержка"},
            {"command": "help", "description": "Помощь"},
        ],
    )
    if MINI_APP_URL.startswith("https://"):
        call(
            "setChatMenuButton",
            menu_button={
                "type": "web_app",
                "text": "Меню",
                "web_app": {"url": MINI_APP_URL},
            },
        )


def run():
    me = call("getMe")
    if not me:
        raise SystemExit(
            "Не удалось подключиться к Telegram. Проверьте токен и интернет/VPN."
        )
    print(f"Бот @{me['username']} запущен. Остановка — Ctrl+C.")
    setup_bot()

    offset = None
    while True:
        params = {"timeout": 30, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            params["offset"] = offset
        updates = call("getUpdates", **params)
        if updates is None:
            time.sleep(3)
            continue
        for update in updates:
            offset = update["update_id"] + 1
            try:
                if "message" in update:
                    handle_message(update["message"])
                elif "callback_query" in update:
                    handle_callback(update["callback_query"])
            except Exception as error:
                print("Ошибка обработки:", error)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nБот остановлен.")
