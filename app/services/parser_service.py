"""
Парсинг цен с сайтов конкурентов через реестр адаптеров CMS.
"""
import logging
from datetime import datetime

import requests
from sqlalchemy.orm import Session

from app.models.competitor import Competitor
from app.models.product import CompetitorProduct, PriceSnapshot
from app.parsers.registry import get_parser_for_url

logger = logging.getLogger(__name__)

# Обратная совместимость для кода, импортирующего REQUEST_HEADERS / fetch_html
from app.parsers.http import REQUEST_HEADERS, fetch_html  # noqa: E402, F401


def is_supported_competitor(competitor: Competitor) -> bool:
    """Проверить, есть ли адаптер для сайта конкурента."""
    url = (competitor.website_url or "").strip()
    if not url:
        return False
    return get_parser_for_url(url) is not None


def parse_product_page(url: str, selector_config: str | None = None):
    """Загрузить и распарсить страницу товара через подходящий адаптер."""
    parser = get_parser_for_url(url)
    if not parser:
        raise ValueError(f"Не найден адаптер для URL: {url}")
    return parser.parse_product(url, selector_config)


def save_price_snapshot(db: Session, competitor_product: CompetitorProduct, parsed) -> PriceSnapshot:
    """
    Сохранить снимок цены в базу данных.
    Обновляет название товара, если на сайте оно изменилось.
    """
    if parsed.name and parsed.name != competitor_product.name:
        competitor_product.name = parsed.name

    snapshot = PriceSnapshot(
        competitor_product_id=competitor_product.id,
        price=parsed.price,
        checked_at=datetime.utcnow(),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def parse_and_save(db: Session, competitor_product: CompetitorProduct) -> PriceSnapshot | None:
    """
    Полный цикл: загрузить страницу, распарсить, сохранить PriceSnapshot.

    Возвращает снимок цены или None при ошибке.
    """
    if not competitor_product.url:
        logger.warning("У товара id=%s нет URL", competitor_product.id)
        return None

    try:
        parsed = parse_product_page(
            competitor_product.url, competitor_product.selector_config
        )
        return save_price_snapshot(db, competitor_product, parsed)
    except requests.RequestException as exc:
        logger.error("Ошибка загрузки %s: %s", competitor_product.url, exc)
        return None
    except ValueError as exc:
        logger.error("Ошибка парсинга %s: %s", competitor_product.url, exc)
        return None
