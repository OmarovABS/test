import hashlib
import hmac
import json
import sys
import time
import urllib.parse

from config import BOT_TOKEN


def build_init_data(user_id, username="", first_name="Test User", auth_date=None):
    user = {"id": user_id, "first_name": first_name}
    if username:
        user["username"] = username
    params = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAE",
        "user": json.dumps(user, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{k}={params[k]}" for k in sorted(params))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(
        secret, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return urllib.parse.urlencode(params)


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is empty. Fill .env first.")
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 123456789
    username = sys.argv[2] if len(sys.argv) > 2 else ""
    print(build_init_data(user_id, username=username))
