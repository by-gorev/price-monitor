"""
Сервис проверки цен конкурентов.

Для BestBalloonn (bestballoonn.ru) — реальный парсинг через parser_service.
Для остальных конкурентов — заглушка с тестовыми данными.
"""
import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import REQUEST_DELAY_SECONDS
from app.models.competitor import Competitor, DeliverySnapshot
from app.models.enums import MatchStatus
from app.models.product import CompetitorProduct, PriceSnapshot
from app.services.parser_service import is_supported_competitor, parse_and_save


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
    parsed_real = 0
    for product in products:
        print("\n" + "=" * 60)
        print(f"ID: {product.id}")
        print(f"NAME: {product.name}")
        print(f"URL: {product.url}")
        print(
            f"COMPETITOR: {product.competitor.name if product.competitor else 'None'}"
        )
        print(
            f"SUPPORTED: {is_supported_competitor(product.competitor) if product.competitor else False}"
        )
        print("=" * 60)

        # Реальный парсинг для BestBalloonn
        # Реальный парсинг для BestBalloonn
        if (
            product.url
            and product.competitor
            and is_supported_competitor(product.competitor)
        ):
            snapshot = parse_and_save(db, product)
            if snapshot:
                checked += 1
                parsed_real += 1
            continue

        # Заглушка для остальных конкурентов
        time.sleep(REQUEST_DELAY_SECONDS)

        last_snapshot = (
            db.query(PriceSnapshot)
            .filter(PriceSnapshot.competitor_product_id == product.id)
            .order_by(PriceSnapshot.checked_at.desc())
            .first()
        )

        if last_snapshot:
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
    message = f"Проверка завершена: {parsed_real} реальных, {checked - parsed_real} заглушка"
    return {"checked": checked, "parsed_real": parsed_real, "message": message}


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
