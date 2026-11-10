import hashlib
import hmac
import json
import urllib.parse

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ADMIN_ID, BOT_TOKEN
from database import get_db
from models import User


def validate_init_data(init_data: str) -> dict | None:
    if not BOT_TOKEN or not init_data:
        return None
    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None
    data_check_string = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received_hash):
        return None
    try:
        user = json.loads(parsed.get("user", "{}"))
    except json.JSONDecodeError:
        return None
    if not user.get("id"):
        return None
    return user


async def current_user(
    x_telegram_init_data: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> User:
    tg_user = validate_init_data(x_telegram_init_data)
    if not tg_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_id = int(tg_user["id"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            id=user_id,
            username=tg_user.get("username"),
            first_name=tg_user.get("first_name"),
            last_name=tg_user.get("last_name"),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


async def current_admin(user: User = Depends(current_user)) -> User:
    if not ADMIN_ID or str(user.id) != ADMIN_ID:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user
