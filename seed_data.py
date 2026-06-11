"""
Скрипт заполнения базы тестовыми данными.
Запуск: python seed_data.py
"""
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models.competitor import Competitor, DeliverySnapshot
from app.models.enums import MatchStatus
from app.models.product import (
    CompetitorProduct,
    MyProduct,
    PriceSnapshot,
    ProductCategory,
)
from app.services.matching import auto_match_products


def seed():
    """Создать тестовые категории, конкурентов, товары и снимки цен."""
    db = SessionLocal()

    try:
        # Проверяем, есть ли уже данные
        if db.query(Competitor).count() > 0:
            print("База уже содержит данные. Пропускаем заполнение.")
            return

        # --- Категории ---
        cat_latex = ProductCategory(name="Латексные шары")
        cat_foil = ProductCategory(name="Фольгированные шары")
        db.add_all([cat_latex, cat_foil])
        db.flush()

        # --- Конкуренты ---
        comp1 = Competitor(name="ШарикМаркет", website_url="https://sharikmarket.example.com")
        comp2 = Competitor(name="ВоздушныеШары.ру", website_url="https://vozdushnye.example.com")
        comp3 = Competitor(name="BalloonShop", website_url="https://balloonshop.example.com")
        db.add_all([comp1, comp2, comp3])
        db.flush()

        # --- Наши эталонные товары ---
        my_products = [
            MyProduct(
                name="Латексный шар без рисунка 30 см",
                category_id=cat_latex.id,
                my_price=25.00,
            ),
            MyProduct(
                name="Латексный шар хром 30 см",
                category_id=cat_latex.id,
                my_price=35.00,
            ),
            MyProduct(
                name="Фольгированный шар сердце 45 см",
                category_id=cat_foil.id,
                my_price=120.00,
            ),
            MyProduct(
                name="Латексный шар конфетти 30 см",
                category_id=cat_latex.id,
                my_price=40.00,
            ),
            MyProduct(
                name="Фольгированная цифра 60 см",
                category_id=cat_foil.id,
                my_price=250.00,
            ),
        ]
        db.add_all(my_products)
        db.flush()

        # --- Товары конкурентов (разные названия для одного эталона) ---
        comp_products = [
            # Аналоги «Латексный шар без рисунка»
            CompetitorProduct(
                competitor_id=comp1.id,
                category_id=cat_latex.id,
                name="Шар пастель 30 см",
                url="https://sharikmarket.example.com/pastel",
                match_status=MatchStatus.UNMATCHED,
            ),
            CompetitorProduct(
                competitor_id=comp2.id,
                category_id=cat_latex.id,
                name="Однотонный латексный шар 30 см",
                url="https://vozdushnye.example.com/odnoton",
                match_status=MatchStatus.UNMATCHED,
            ),
            CompetitorProduct(
                competitor_id=comp3.id,
                category_id=cat_latex.id,
                name="Гелиевый шар без рисунка 30 см",
                url="https://balloonshop.example.com/plain",
                match_status=MatchStatus.UNMATCHED,
            ),
            # Аналоги «хром»
            CompetitorProduct(
                competitor_id=comp1.id,
                category_id=cat_latex.id,
                name="Шар хром золото 30 см",
                url="https://sharikmarket.example.com/chrome",
                match_status=MatchStatus.UNMATCHED,
            ),
            CompetitorProduct(
                competitor_id=comp2.id,
                category_id=cat_latex.id,
                name="Хромированный шар 30 см",
                url="https://vozdushnye.example.com/chrome",
                match_status=MatchStatus.UNMATCHED,
            ),
            # Аналоги «сердце»
            CompetitorProduct(
                competitor_id=comp1.id,
                category_id=cat_foil.id,
                name="Фольга сердце 45 см красное",
                url="https://sharikmarket.example.com/heart",
                match_status=MatchStatus.UNMATCHED,
            ),
            # Аналоги «конфетти»
            CompetitorProduct(
                competitor_id=comp3.id,
                category_id=cat_latex.id,
                name="Латекс конфетти 30 см",
                url="https://balloonshop.example.com/confetti",
                match_status=MatchStatus.UNMATCHED,
            ),
            # Неочевидное совпадение — останется UNMATCHED
            CompetitorProduct(
                competitor_id=comp2.id,
                category_id=cat_foil.id,
                name="Декоративный элемент для праздника",
                url="https://vozdushnye.example.com/deco",
                match_status=MatchStatus.UNMATCHED,
            ),
        ]
        db.add_all(comp_products)
        db.flush()

        db.commit()

        # Автоматическое сопоставление по названиям
        matched = auto_match_products(db)
        print(f"Авто-сопоставлено товаров: {matched}")

        # Добавляем начальные снимки цен для сопоставленных товаров
        db.expire_all()
        matched_products = (
            db.query(CompetitorProduct)
            .filter(
                CompetitorProduct.match_status.in_(
                    [MatchStatus.AUTO_MATCHED, MatchStatus.MANUAL_MATCHED]
                )
            )
            .all()
        )

        base_time = datetime.utcnow() - timedelta(days=1)
        for i, product in enumerate(matched_products):
            # Старый снимок
            db.add(
                PriceSnapshot(
                    competitor_product_id=product.id,
                    price=80.0 + i * 5,
                    checked_at=base_time,
                )
            )
            # Новый снимок (с изменением)
            db.add(
                PriceSnapshot(
                    competitor_product_id=product.id,
                    price=85.0 + i * 5,
                    checked_at=datetime.utcnow(),
                )
            )

        # Снимки доставки
        for i, comp in enumerate([comp1, comp2, comp3]):
            db.add(
                DeliverySnapshot(
                    competitor_id=comp.id,
                    delivery_price=300.0 + i * 50,
                    description=f"Доставка от {300 + i * 50} руб. по городу",
                    checked_at=datetime.utcnow(),
                )
            )

        db.commit()
        print("Тестовые данные успешно добавлены!")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
