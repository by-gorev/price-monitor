"""
Общие стратегии парсинга страницы товара.
"""
import json
import re

from bs4 import BeautifulSoup

from app.parsers.html_utils import iter_schema_nodes
from app.parsers.parser_types import ParsedProduct
from app.parsers.utils import parse_price_value


def parse_from_selectors(html: str, selectors: dict) -> ParsedProduct | None:
    soup = BeautifulSoup(html, "html.parser")
    name = ""
    if selectors.get("name"):
        el = soup.select_one(selectors["name"])
        if el:
            name = el.get_text(strip=True)

    price = None
    if selectors.get("price"):
        el = soup.select_one(selectors["price"])
        if el:
            attr = el.get("data-product-price-def") or el.get("content")
            if attr:
                price = parse_price_value(str(attr))
            if price is None:
                price = parse_price_value(el.get_text())

    if price is None and selectors.get("price_meta"):
        meta = soup.select_one(selectors["price_meta"])
        if meta and meta.get("content"):
            price = parse_price_value(meta["content"])

    if name and price is not None:
        return ParsedProduct(name=name, price=price)
    return None


def parse_from_opengraph(html: str) -> ParsedProduct | None:
    soup = BeautifulSoup(html, "html.parser")
    name = ""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        name = og_title["content"].split(" - ")[0].strip()

    price = None
    for prop in ("product:price:amount", "og:price:amount"):
        meta = soup.find("meta", property=prop)
        if meta and meta.get("content"):
            price = parse_price_value(meta["content"])
            if price is not None:
                break

    if name and price is not None:
        return ParsedProduct(name=name, price=price)
    return None


def parse_from_schema_org(html: str) -> ParsedProduct | None:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in iter_schema_nodes(data):
            node_type = node.get("@type", "")
            types = node_type if isinstance(node_type, list) else [node_type]
            if "Product" not in types:
                continue
            name = (node.get("name") or "").strip()
            offers = node.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price_raw = offers.get("price") or node.get("price")
            price = parse_price_value(str(price_raw)) if price_raw is not None else None
            if name and price is not None:
                return ParsedProduct(name=name, price=price)
    return None


def parse_from_itemprop(html: str) -> ParsedProduct | None:
    soup = BeautifulSoup(html, "html.parser")
    name_el = soup.find(itemprop="name")
    price_el = soup.find(itemprop="price")
    name = name_el.get_text(strip=True) if name_el else ""
    price = None
    if price_el:
        content = price_el.get("content") or price_el.get_text()
        price = parse_price_value(str(content))
    if name and price is not None:
        return ParsedProduct(name=name, price=price)
    return None


def parse_from_embedded_json(html: str) -> ParsedProduct | None:
    patterns = (
        r"var\s+product\s*=\s*(\{.*?\});",
        r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});",
        r"window\.product\s*=\s*(\{.*?\});",
    )
    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)
        if not match:
            continue
        try:
            data = json.loads(match.group(1))
        except (json.JSONDecodeError, TypeError):
            continue
        name = (data.get("title") or data.get("name") or "").strip()
        price_raw = data.get("price") or data.get("price_value")
        if price_raw is None and isinstance(data.get("offers"), dict):
            price_raw = data["offers"].get("price")
        price = parse_price_value(str(price_raw)) if price_raw is not None else None
        if name and price is not None:
            return ParsedProduct(name=name, price=price)
    return None


def parse_product_page(
    html: str,
    url: str,
    selectors: dict | None,
    strategies: list | None = None,
) -> ParsedProduct:
    """Последовательный запуск стратегий парсинга товара."""
    if selectors:
        result = parse_from_selectors(html, selectors)
        if result:
            return result

    for item in strategies or []:
        strategy_fn = item[1] if isinstance(item, tuple) else item
        result = strategy_fn(html)
        if result:
            return result

    for fn in (
        parse_from_schema_org,
        parse_from_opengraph,
        parse_from_itemprop,
        parse_from_embedded_json,
    ):
        result = fn(html)
        if result:
            return result

    raise ValueError(f"Не удалось извлечь название или цену со страницы: {url}")
