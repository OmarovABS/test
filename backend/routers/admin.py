from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth import current_admin
from database import get_db
from models import Order, Product, User
from routers.orders import STATUS_LABELS, order_dict

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
async def stats(
    admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)
):
    total_orders = await db.scalar(select(func.count(Order.id)))
    total_revenue = await db.scalar(
        select(func.coalesce(func.sum(Order.total), 0))
    )
    active = await db.scalar(
        select(func.count(Order.id)).where(
            Order.status.in_(["accepted", "cooking", "delivery"])
        )
    )
    users_count = await db.scalar(select(func.count(User.id)))
    products_count = await db.scalar(select(func.count(Product.id)))
    return {
        "orders": total_orders or 0,
        "revenue": int(total_revenue or 0),
        "active_orders": active or 0,
        "users": users_count or 0,
        "products": products_count or 0,
    }


@router.get("/orders")
async def all_orders(
    admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.user))
        .order_by(Order.created_at.desc())
        .limit(100)
    )
    return [order_dict(o, with_user=True) for o in result.scalars().all()]


class StatusIn(BaseModel):
    status: str


@router.patch("/orders/{order_id}")
async def set_status(
    order_id: int,
    payload: StatusIn,
    admin: User = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    if payload.status not in STATUS_LABELS:
        raise HTTPException(status_code=400, detail="Unknown status")
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = payload.status
    await db.commit()
    return {"ok": True, "status": order.status}


@router.get("/products")
async def all_products(
    admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Product).order_by(Product.category, Product.sort, Product.id)
    )
    return [
        {
            "id": p.id,
            "category": p.category,
            "name": p.name,
            "description": p.description or "",
            "price": p.price,
            "image": p.image or "",
            "in_stock": p.in_stock,
            "sort": p.sort,
        }
        for p in result.scalars().all()
    ]


class ProductIn(BaseModel):
    category: str
    name: str
    description: str | None = None
    price: int
    image: str | None = None
    in_stock: bool = True
    sort: int = 0


@router.post("/products", status_code=201)
async def create_product(
    payload: ProductIn,
    admin: User = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    product = Product(**payload.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return {"id": product.id}


@router.patch("/products/{product_id}")
async def update_product(
    product_id: int,
    payload: ProductIn,
    admin: User = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for key, value in payload.model_dump().items():
        setattr(product, key, value)
    await db.commit()
    return {"ok": True}


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: int,
    admin: User = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(product)
    await db.commit()
    return {"ok": True}
