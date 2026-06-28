"""
Скрипт начального наполнения базы.
Запуск: python seed_data.py

Полностью очищает таблицы приложения (кроме alembic_version),
затем создаёт рыночные категории и конкурента BestBalloonn.
Тестовые товары, цены и история не добавляются.
"""
from sqlalchemy import text

from app.database import SessionLocal, engine
from app.models.competitor import Competitor
from app.models.product import ProductCategory

# Таблицы приложения (порядок не важен при TRUNCATE ... CASCADE)
APP_TABLES = (
    "price_snapshots",
    "competitor_products",
    "competitor_categories",
    "delivery_snapshots",
    "product_categories",
    "competitors",
)

# Рыночные категории: (название, ключевые слова через запятую)
MARKET_CATEGORIES = [
    ("Латекс пастель", "пастель, однотон, однотонный"),
    ("Латекс хром", "хром, chrome, хромирован"),
    ("Цифра 102 см", "цифра, 102"),
    ("Большие сердца и звёзды", "сердце, сердца, звезда, звёзд, звезд, фольгированн"),
    ("стеклянный шар", "стекл, баббл, bubble, babble"),
    ("Сфера", "сфера, круг 90, 90 см"),
    ("Доставка", "доставк"),
]


def clear_database() -> None:
    """Удалить все данные из таблиц приложения. alembic_version не трогаем."""
    tables = ", ".join(APP_TABLES)
    with engine.begin() as conn:
        conn.execute(
            text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE")
        )
    print("Таблицы очищены:", ", ".join(APP_TABLES))


def seed() -> None:
    """Очистить БД и создать категории + конкурента BestBalloonn."""
    clear_database()

    db = SessionLocal()
    try:
        for name, keywords in MARKET_CATEGORIES:
            db.add(ProductCategory(name=name, my_price=0, keywords=keywords))

        db.add(
            Competitor(
                name="BestBalloonn",
                website_url="https://bestballoonn.ru",
            )
        )

        db.commit()
        print(f"Добавлено категорий: {len(MARKET_CATEGORIES)}")
        print("Добавлен конкурент: BestBalloonn")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
