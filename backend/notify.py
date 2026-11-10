import asyncio
import html

import httpx

from config import ADMIN_ID, BOT_TOKEN


def fmt_sum(value: int) -> str:
    return f"{value:,}".replace(",", " ")


async def send_admin_message(text: str):
    if not BOT_TOKEN or not ADMIN_ID:
        return
    try:
        chat_id = int(ADMIN_ID)
    except ValueError:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
    except Exception as error:
        print(f"[notify] {error}")


def notify_admin_order(order, user) -> asyncio.Task | None:
    items = "\n".join(
        f"• {html.escape(i.name)} ×{i.qty} — {fmt_sum(i.price * i.qty)} сум"
        for i in order.items
    )
    name = " ".join(
        part for part in (user.first_name, user.last_name) if part
    ).strip() or "Без имени"
    username = f"@{user.username}" if user.username else "—"
    address = html.escape(order.address) if order.address else "—"
    text = (
        "🆕 <b>Новый заказ</b>\n\n"
        f"🧾 Заказ <b>#{order.id}</b>\n"
        f"👤 {html.escape(name)} ({html.escape(username)})\n"
        f"🆔 <code>{user.id}</code>\n\n"
        f"{items}\n\n"
        f"💰 Итого: <b>{fmt_sum(order.total)}</b> сум\n"
        + f"📍 Адрес: {address}"
    )
    return asyncio.create_task(send_admin_message(text))
