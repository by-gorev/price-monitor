"""
Парсинг цен с сайта конкурента BestBalloonn (bestballoonn.ru).

Сайт построен на Tilda Store. На странице товара (/tproduct/...)
название и цена доступны в HTML без JavaScript.

Поддерживается только один конкурент — домен bestballoonn.ru.
"""
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.config import REQUEST_DELAY_SECONDS
from app.models.competitor import Competitor
from app.models.product import CompetitorProduct, PriceSnapshot

logger = logging.getLogger(__name__)

# Домен единственного поддерживаемого конкурента
SUPPORTED_DOMAIN = "bestballoonn.ru"

# CSS-селекторы для страниц товаров Tilda Store на bestballoonn.ru
DEFAULT_SELECTORS = {
    "name": "h1.js-product-name",
    "price": ".js-product-price",
    "price_meta": "meta[itemprop='price']",
}

# Заголовки запроса — сайт отдаёт 403 без нормального User-Agent
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": "https://bestballoonn.ru/",
}


@dataclass
class ParsedProduct:
    """Результат парсинга страницы товара."""

    name: str
    price: float


def is_supported_competitor(competitor: Competitor) -> bool:
    """Проверить, поддерживается ли парсинг для данного конкурента."""
    return SUPPORTED_DOMAIN in (competitor.website_url or "").lower()


def _load_selectors(selector_config: str | None) -> dict:
    """
    Загрузить CSS-селекторы из JSON-поля selector_config.
    Если не задано — используются селекторы по умолчанию для BestBalloonn.
    """
    if not selector_config:
        return DEFAULT_SELECTORS.copy()
    try:
        custom = json.loads(selector_config)
        selectors = DEFAULT_SELECTORS.copy()
        selectors.update(custom)
        return selectors
    except json.JSONDecodeError:
        logger.warning("Некорректный selector_config, используем значения по умолчанию")
        return DEFAULT_SELECTORS.copy()


def fetch_html(url: str) -> str:
    """
    Загрузить HTML страницы товара.
    Между запросами выдерживается задержка REQUEST_DELAY_SECONDS.
    """
    import time

    time.sleep(REQUEST_DELAY_SECONDS)

    response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def _parse_price_value(text: str) -> float | None:
    """
    Преобразовать строку цены в число.
    Поддерживает форматы: «850,00», «850.00», «850 р.».
    """
    if not text:
        return None
    cleaned = re.sub(r"[^\d,.\-]", "", text.strip())
    cleaned = cleaned.replace(",", ".")
    # Если несколько точек — оставляем только последнюю как десятичный разделитель
    if cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_from_tilda_json(html: str) -> ParsedProduct | None:
    """
    Запасной способ: извлечь данные из встроенного JSON «var product = {...}».
    Tilda всегда вставляет этот объект на странице товара.
    """
    match = re.search(r"var\s+product\s*=\s*(\{.*?\});", html, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
        name = (data.get("title") or "").strip()
        price = _parse_price_value(str(data.get("price", "")))
        if name and price is not None:
            return ParsedProduct(name=name, price=price)
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def parse_product_html(html: str, selector_config: str | None = None) -> ParsedProduct:
    """
    Распарсить HTML страницы товара BestBalloonn.

    Порядок извлечения:
    1. CSS-селекторы через BeautifulSoup
    2. meta[itemprop='price'] и data-product-price-def
    3. Встроенный JSON Tilda (var product = ...)
    """
    selectors = _load_selectors(selector_config)
    soup = BeautifulSoup(html, "html.parser")

    # --- Название товара ---
    name = ""
    name_el = soup.select_one(selectors["name"])
    if name_el:
        name = name_el.get_text(strip=True)

    if not name:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            name = og_title["content"].split(" - ")[0].strip()

    # --- Цена товара ---
    price: float | None = None

    price_el = soup.select_one(selectors["price"])
    if price_el:
        # Сначала атрибут data-product-price-def (точное значение)
        attr_price = price_el.get("data-product-price-def")
        if attr_price:
            price = _parse_price_value(attr_price)
        if price is None:
            price = _parse_price_value(price_el.get_text())

    if price is None:
        meta_el = soup.select_one(selectors["price_meta"])
        if meta_el and meta_el.get("content"):
            price = _parse_price_value(meta_el["content"])

    if name and price is not None:
        return ParsedProduct(name=name, price=price)

    # Запасной вариант — JSON из скрипта Tilda
    fallback = _parse_from_tilda_json(html)
    if fallback:
        return fallback

    raise ValueError("Не удалось извлечь название или цену со страницы")


def parse_product_page(url: str, selector_config: str | None = None) -> ParsedProduct:
    """Загрузить и распарсить страницу товара по URL."""
    html = fetch_html(url)
    return parse_product_html(html, selector_config)


def save_price_snapshot(
    db: Session, competitor_product: CompetitorProduct, parsed: ParsedProduct
) -> PriceSnapshot:
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
