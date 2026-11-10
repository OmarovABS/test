from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Product

router = APIRouter(tags=["menu"])


@router.get("/api/menu")
async def get_menu(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Product)
        .where(Product.in_stock.is_(True))
        .order_by(Product.category, Product.sort, Product.id)
    )
    products = result.scalars().all()

    categories = []
    seen = set()
    for p in products:
        if p.category not in seen:
            seen.add(p.category)
            categories.append(p.category)

    return {
        "categories": categories,
        "products": [
            {
                "id": p.id,
                "category": p.category,
                "name": p.name,
                "description": p.description or "",
                "price": p.price,
                "image": p.image or "",
            }
            for p in products
        ],
    }
