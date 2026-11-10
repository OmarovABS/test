from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth import ADMIN_ID, current_user
from database import get_db
from models import Order, OrderItem, Product, User
from notify import notify_admin_order

router = APIRouter(tags=["orders"])

STATUS_LABELS = {
    "accepted": "Принят",
    "cooking": "Готовится",
    "delivery": "В пути",
    "delivered": "Доставлен",
    "cancelled": "Отменён",
}


def order_dict(order: Order, with_user: bool = False) -> dict:
    data = {
        "id": order.id,
        "status": order.status,
        "status_label": STATUS_LABELS.get(order.status, order.status),
        "total": order.total,
        "address": order.address,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "items": [
            {"name": i.name, "price": i.price, "qty": i.qty} for i in order.items
        ],
    }
    if with_user and order.user:
        u = order.user
        data["user"] = {
            "id": u.id,
            "name": " ".join(x for x in (u.first_name, u.last_name) if x) or "Без имени",
            "username": u.username,
        }
    return data


class OrderItemIn(BaseModel):
    product_id: int
    qty: int


class OrderIn(BaseModel):
    items: list[OrderItemIn]
    address: str | None = None


@router.get("/api/me")
async def me(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    orders_count = await db.scalar(
        select(func.count(Order.id)).where(Order.user_id == user.id)
    )
    total_sum = await db.scalar(
        select(func.coalesce(func.sum(Order.total), 0)).where(Order.user_id == user.id)
    )
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_admin": bool(ADMIN_ID) and str(user.id) == ADMIN_ID,
        "orders_count": orders_count or 0,
        "total_sum": int(total_sum or 0),
    }


@router.post("/api/orders", status_code=201)
async def create_order(
    payload: OrderIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Empty order")

    ids = [i.product_id for i in payload.items]
    result = await db.execute(select(Product).where(Product.id.in_(ids)))
    products = {p.id: p for p in result.scalars().all()}

    order = Order(user_id=user.id, address=payload.address, status="accepted")
    total = 0
    for item in payload.items:
        product = products.get(item.product_id)
        if not product or not product.in_stock:
            raise HTTPException(status_code=400, detail=f"Product {item.product_id} unavailable")
        qty = max(1, min(item.qty, 99))
        order.items.append(
            OrderItem(
                product_id=product.id,
                name=product.name,
                price=product.price,
                qty=qty,
            )
        )
        total += product.price * qty
    order.total = total

    db.add(order)
    await db.commit()
    notify_admin_order(order, user)
    return order_dict(order)


@router.get("/api/orders/me")
async def my_orders(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .limit(50)
    )
    return [order_dict(o) for o in result.scalars().all()]
