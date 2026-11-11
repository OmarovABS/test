from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl
from typing import Any


def verify_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = 86400,
    now: int | None = None,
) -> dict[str, Any] | None:
    """Verify Telegram Mini App initData and return its decoded user, if valid."""
    if not init_data or not bot_token or len(init_data) > 8192:
        return None
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
        values = dict(pairs)
        if len(values) != len(pairs):
            return None
        received_hash = values.pop("hash", "")
        if len(received_hash) != 64:
            return None
        check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calculated_hash, received_hash):
            return None
        auth_date = int(values.get("auth_date", "0"))
        current_time = int(time.time()) if now is None else now
        if auth_date <= 0 or auth_date > current_time + 60 or current_time - auth_date > max_age_seconds:
            return None
        user = json.loads(values.get("user", "{}"))
        if not isinstance(user, dict) or not isinstance(user.get("id"), int):
            return None
        return user
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
