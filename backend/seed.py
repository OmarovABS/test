from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Product

SEED_PRODUCTS = [
    # Донар
    ("Донар", "Донар классик", "Говядина, свежие овощи, лаваш", 32000, "images/donar-klassik.jpg", 1),
    ("Донар", "Донар куриный", "Курица на гриле, соус, салат", 28000, "images/donar-kurinyy.jpg", 2),
    ("Донар", "Донар XL", "Двойная порция мяса и сыр", 42000, "images/donar-xl.jpg", 3),
    # Бургер
    ("Бургер", "Чизбургер", "Говяжья котлета, чеддер, томат", 35000, "images/chizburger.jpg", 1),
    ("Бургер", "Биг бургер", "Две котлеты, лук, фирменный соус", 48000, "images/big-burger.jpg", 2),
    # Хот-дог
    ("Хот-дог", "Хот-дог классик", "Сосиска, горчица, булочка бриошь", 18000, "images/hot-dog-klassik.jpg", 1),
    ("Хот-дог", "Хот-дог датский", "Хрустящий лук, огурчики", 22000, "images/hot-dog-datskiy.jpg", 2),
    # Напитки
    ("Напитки", "Лимонад", "Лимон, мята, лёд", 15000, "images/limonad.jpg", 1),
    ("Напитки", "Айран", "Освежающий, домашний", 9000, "images/ayran.jpg", 2),
    # Пицца
    ("Пицца", "Пепперони", "Пепперони, моцарелла, томатный соус", 75000, "images/pepperoni.jpg", 1),
    ("Пицца", "Маргарита", "Моцарелла, томаты, базилик", 62000, "images/margarita.jpg", 2),
]


async def seed_products(db: AsyncSession):
    count = await db.scalar(select(func.count(Product.id)))
    if count:
        return
    for category, name, desc, price, image, sort in SEED_PRODUCTS:
        db.add(
            Product(
                category=category,
                name=name,
                description=desc,
                price=price,
                image=image,
                in_stock=True,
                sort=sort,
            )
        )
    await db.commit()
