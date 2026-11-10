from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import SessionLocal, init_db
from routers import admin, menu, orders
from seed import seed_products

ROOT_DIR = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with SessionLocal() as db:
        await seed_products(db)
    yield


app = FastAPI(title="Premium Food API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(menu.router)
app.include_router(orders.router)
app.include_router(admin.router)


@app.get("/api/health")
async def health():
    return {"ok": True}


app.mount("/", StaticFiles(directory=ROOT_DIR, html=True), name="static")
