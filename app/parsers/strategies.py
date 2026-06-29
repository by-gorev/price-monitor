"""
Общие стратегии поиска товаров на странице категории.
"""
import json
import re
from collections.abc import Callable
from urllib.parse import urlparse

import requests

from app.parsers.html_utils import iter_schema_nodes
from app.parsers.parser_types import ScanResult, ScannedItem
from app.parsers.http import fetch_json
from app.parsers.page_context import PageContext
from app.parsers.utils import normalize_url, parse_price_value


def _extract_listing_price(product: dict) -> float | None:
    for key in ("price", "price_value", "amount"):
        if product.get(key) is not None:
            return parse_price_value(str(product[key]))
    return None


def collect_candidates(
    candidates: list[tuple[str, str]],
    base: str,
    url_filter: Callable[[str], bool] | None = None,
) -> ScanResult:
    """Собрать уникальные товары из кандидатов (href, name)."""
    seen: set[str] = set()
    items: list[ScannedItem] = []
    rejected = 0
    raw = len(candidates)

    for href, name in candidates:
        normalized = normalize_url(href, base)
        if not normalized:
            rejected += 1
            continue
        if url_filter and not url_filter(normalized):
            rejected += 1
            continue
        if normalized in seen:
            rejected += 1
            continue
        clean_name = name.strip()
        if not clean_name:
            rejected += 1
            continue
        seen.add(normalized)
        items.append(ScannedItem(name=clean_name, url=normalized))

    return ScanResult(items=items, rejected_links=rejected, raw_candidates=raw)


def schema_org_products(ctx: PageContext) -> ScanResult:
    """JSON-LD schema.org Product / ItemList."""
    candidates: list[tuple[str, str]] = []
    for script in ctx.soup.find_all("script", type="application/ld+json"):
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

            if "Product" in types:
                url = node.get("url") or node.get("@id") or ""
                name = node.get("name") or ""
                if url and name:
                    candidates.append((url, name))

            if "ItemList" in types:
                for element in node.get("itemListElement", []):
                    item = element.get("item", element)
                    if not isinstance(item, dict):
                        continue
                    url = item.get("url") or item.get("@id") or ""
                    name = item.get("name") or ""
                    if url and name:
                        candidates.append((url, name))

    return collect_candidates(candidates, ctx.base)


def product_url_patterns(
    ctx: PageContext,
    patterns: tuple[str, ...],
    path_keywords: tuple[str, ...] | None = None,
) -> ScanResult:
    """Поиск ссылок по шаблонам URL и ключевым словам пути."""
    candidates: list[tuple[str, str]] = []
    keywords = path_keywords or ()

    for link in ctx.soup.find_all("a", href=True):
        href = link["href"]
        href_lower = href.lower()
        matched = any(p in href_lower for p in patterns)
        if not matched and keywords:
            matched = any(kw in href_lower for kw in keywords)
        if matched:
            candidates.append((href, link.get_text(strip=True)))

    def url_filter(url: str) -> bool:
        lower = url.lower()
        if any(p in lower for p in patterns):
            return True
        return any(kw in lower for kw in keywords) if keywords else True

    return collect_candidates(candidates, ctx.base, url_filter=url_filter)


def product_card_selectors(
    ctx: PageContext,
    selectors: tuple[str, ...],
    url_filter: Callable[[str], bool] | None = None,
) -> ScanResult:
    """Поиск карточек товара по CSS-селекторам."""
    candidates: list[tuple[str, str]] = []

    for selector in selectors:
        for el in ctx.soup.select(selector):
            if el.name == "a" and el.get("href"):
                candidates.append((el["href"], el.get_text(strip=True)))
                continue
            link = el.find("a", href=True)
            if not link:
                continue
            title_el = el.select_one(
                "h1, h2, h3, h4, .title, .name, .product-name, .card-title, .product-title"
            )
            name = title_el.get_text(strip=True) if title_el else link.get_text(strip=True)
            candidates.append((link["href"], name))

    return collect_candidates(candidates, ctx.base, url_filter=url_filter)


def embedded_json_products(
    ctx: PageContext,
    patterns: tuple[str, ...] = (
        r'"products"\s*:\s*(\[[\s\S]*?\])\s*[,}]',
        r'"items"\s*:\s*(\[[\s\S]*?\])\s*[,}]',
        r'var\s+products\s*=\s*(\[[\s\S]*?\]);',
    ),
) -> ScanResult:
    """Встроенный JSON со списком товаров в скриптах страницы."""
    items: list[ScannedItem] = []
    rejected = 0
    raw = 0
    seen: set[str] = set()

    for pattern in patterns:
        for match in re.finditer(pattern, ctx.html):
            try:
                products = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            if not isinstance(products, list):
                continue
            for product in products:
                raw += 1
                if not isinstance(product, dict):
                    rejected += 1
                    continue
                name = (
                    product.get("title")
                    or product.get("name")
                    or product.get("product_title")
                    or ""
                ).strip()
                url = (
                    product.get("url")
                    or product.get("link")
                    or product.get("href")
                    or product.get("handle")
                    or ""
                )
                if isinstance(url, str) and url and not url.startswith("http"):
                    if url.startswith("/"):
                        url = normalize_url(url, ctx.base)
                    elif "handle" in product:
                        url = normalize_url(f"/products/{url}", ctx.base)
                url = str(url).strip()
                if not name or not url:
                    rejected += 1
                    continue
                if url in seen:
                    rejected += 1
                    continue
                seen.add(url)
                price = _extract_listing_price(product)
                items.append(ScannedItem(name=name, url=url, price=price))

    return ScanResult(items=items, rejected_links=rejected, raw_candidates=raw)


def fetch_json_api(
    ctx: PageContext,
    build_urls: Callable[[PageContext], list[str]],
    map_item: Callable[[dict, str], ScannedItem | None],
) -> ScanResult:
    """Загрузка товаров из публичного JSON API."""
    items: list[ScannedItem] = []
    rejected = 0
    raw = 0
    seen: set[str] = set()

    for api_url in build_urls(ctx):
        try:
            data = fetch_json(api_url, referer=ctx.url)
        except (requests.RequestException, ValueError, json.JSONDecodeError):
            continue

        products = data.get("products") or data.get("items") or data
        if isinstance(products, dict):
            products = products.get("products") or products.get("items") or []
        if not isinstance(products, list):
            continue

        for product in products:
            raw += 1
            if not isinstance(product, dict):
                rejected += 1
                continue
            item = map_item(product, ctx.base)
            if not item:
                rejected += 1
                continue
            if item.url in seen:
                rejected += 1
                continue
            seen.add(item.url)
            items.append(item)

        if items:
            break

    return ScanResult(items=items, rejected_links=rejected, raw_candidates=raw)


def generic_product_like_links(ctx: PageContext) -> ScanResult:
    """Универсальный поиск ссылок, похожих на карточки товара."""
    keywords = (
        "product", "tovar", "tproduct", "item", "catalog", "shop",
        "товар", "каталог", "шар", "balloon",
    )
    exclude = (
        "cart", "checkout", "login", "register", "account", "policy",
        "contact", "about", "blog", "news", "faq", "#", "javascript:",
    )
    candidates: list[tuple[str, str]] = []

    for link in ctx.soup.find_all("a", href=True):
        href = link["href"].lower()
        if any(ex in href for ex in exclude):
            continue
        if any(kw in href for kw in keywords):
            name = link.get_text(strip=True)
            if len(name) >= 3:
                candidates.append((link["href"], name))

    return collect_candidates(candidates, ctx.base)


def generic_cms_cards(ctx: PageContext) -> ScanResult:
    """Распространённые CSS-селекторы карточек популярных CMS."""
    selectors = (
        ".product", ".product-item", ".product-card", ".product-layout",
        ".catalog-item", ".item-product", ".goods-item", ".shop-item",
        ".woocommerce-loop-product", ".product-grid-item",
        "[class*='product-card']", "[class*='product_item']",
        "[data-product-id]", "[data-product-url]",
    )
    return product_card_selectors(ctx, selectors)


def collection_products_json(ctx: PageContext, suffix: str = "/products.json") -> ScanResult:
    """Shopify-подобный products.json для текущего пути коллекции."""
    parsed = urlparse(ctx.url)
    path = parsed.path.rstrip("/")

    candidates_urls = []
    if path:
        candidates_urls.append(f"{ctx.base}{path}{suffix}")
    candidates_urls.append(f"{ctx.base}/products.json")

    def map_shopify(product: dict, base: str) -> ScannedItem | None:
        title = (product.get("title") or "").strip()
        handle = (product.get("handle") or "").strip()
        url = product.get("url") or ""
        if not url and handle:
            url = f"{base}/products/{handle}"
        if title and url:
            return ScannedItem(name=title, url=url)
        return None

    return fetch_json_api(
        ctx,
        build_urls=lambda c: candidates_urls,
        map_item=map_shopify,
    )
