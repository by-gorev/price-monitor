"""
Сервис проверки цен конкурентов.

Сейчас — заглушка: сохраняет тестовые снимки цен.
Реальный парсинг сайтов будет добавлен на следующем шаге.
"""
import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import REQUEST_DELAY_SECONDS
from app.models.competitor import Competitor, DeliverySnapshot
from app.models.enums import MatchStatus
from app.models.product import CompetitorProduct, PriceSnapshot


def check_prices(db: Session) -> dict:
    """
    Проверить цены всех сопоставленных товаров конкурентов.

    Заглушка: для каждого товара с URL генерирует случайное изменение
    относительно последней известной цены (или фиксированную цену).

    Между «запросами» выдерживается задержка REQUEST_DELAY_SECONDS.
    """
    products = (
        db.query(CompetitorProduct)
        .filter(
            CompetitorProduct.match_status.in_(
                [MatchStatus.AUTO_MATCHED, MatchStatus.MANUAL_MATCHED]
            )
        )
        .all()
    )

    checked = 0
    for product in products:
        # Задержка между запросами (имитация парсинга)
        time.sleep(REQUEST_DELAY_SECONDS)

        # Заглушка: берём последнюю цену или ставим 100 руб.
        last_snapshot = (
            db.query(PriceSnapshot)
            .filter(PriceSnapshot.competitor_product_id == product.id)
            .order_by(PriceSnapshot.checked_at.desc())
            .first()
        )

        if last_snapshot:
            # Небольшое случайное изменение для демонстрации
            import random

            change = random.choice([-10, -5, 0, 5, 10])
            new_price = max(float(last_snapshot.price) + change, 1.0)
        else:
            new_price = 100.0

        snapshot = PriceSnapshot(
            competitor_product_id=product.id,
            price=new_price,
            checked_at=datetime.utcnow(),
        )
        db.add(snapshot)
        checked += 1

    db.commit()
    return {"checked": checked, "message": "Проверка завершена (режим заглушки)"}


def check_delivery(db: Session) -> dict:
    """
    Проверить условия доставки всех конкурентов.
    Заглушка — сохраняет тестовые данные.
    """
    competitors = db.query(Competitor).all()
    checked = 0

    for competitor in competitors:
        time.sleep(REQUEST_DELAY_SECONDS)

        snapshot = DeliverySnapshot(
            competitor_id=competitor.id,
            delivery_price=300.0 + checked * 50,
            description="Доставка по городу от 300 руб. (тестовые данные)",
            checked_at=datetime.utcnow(),
        )
        db.add(snapshot)
        checked += 1

    db.commit()
    return {"checked": checked, "message": "Проверка доставки завершена (режим заглушки)"}
