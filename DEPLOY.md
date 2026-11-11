# Deploy guide

## Render deployment

1. Push this project to GitHub.
2. Create a new Render service connected to the repository.
3. Choose "Web Service" and set the root folder.
4. Render will use `render.yaml` automatically.
5. Add the environment variables in the Render dashboard:
   - BOT_TOKEN
   - ADMIN_ID
   - ADMIN_CHAT_ID
   - ADMIN_IDS
   - MINI_APP_URL
   - SUPPORT_USERNAME
   - RESTAURANT_NAME
   - DEBUG_MODE=False
   - DATABASE_PATH=delivery.db
6. After deployment, set `MINI_APP_URL` to the public HTTPS URL of the web service.
7. If you want Telegram notifications, keep the bot running via the worker service.

## Notes

- The app serves both the storefront and the FastAPI API from the same origin.
- The database file is created at runtime.
- The bot and API should use the same `BOT_TOKEN` and admin IDs.
- For production, do not expose `.env` in the repository.
