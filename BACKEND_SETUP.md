# FastAPI backend and admin panel

## Local run

1. Install dependencies with `pip install -r requirements.txt` (or use the existing `.venv`).
2. Keep the bot token private in `.env`. The backend accepts `ADMIN_CHAT_ID`, `ADMIN_IDS` (comma-separated Telegram numeric user IDs), `DEBUG_MODE`, `DATABASE_PATH`, and `RESTAURANT_NAME`. For compatibility with the current project, if `ADMIN_CHAT_ID` or `ADMIN_IDS` is missing, the old `ADMIN_ID` value is used.
3. Run `run_api.bat` and open `http://127.0.0.1:8000`. The first run creates `delivery.db` in the project directory and seeds the 11 current menu items.
4. Local `.env` uses `DEBUG_MODE=True` only for loopback browser testing. Set `DEBUG_MODE=False` in production. Production admin access requires valid Telegram `initData` and an ID listed in `ADMIN_IDS`.
5. The bot process can continue running separately with `run_bot.bat`; the Mini App now posts orders to FastAPI instead of using Telegram `sendData`.

## Production deployment

GitHub Pages is static hosting and cannot run FastAPI. Deploy this Python app to a server/platform with persistent disk, configure HTTPS, and preferably serve the frontend and API on the same origin (or put them behind a reverse proxy). Point the Telegram Mini App URL to that HTTPS deployment, not the GitHub Pages URL. Configure `BOT_TOKEN`, `ADMIN_CHAT_ID`, `ADMIN_IDS`, `DEBUG_MODE=False`, and a persistent `DATABASE_PATH` on the host. Back up `delivery.db` and `static/uploads/`.

Uploaded photos and the SQLite database are runtime data; both are excluded from Git. Do not commit `.env` or expose `BOT_TOKEN` in frontend code.
