"""
Универсальный парсер сайтов на Tilda / Tilda Store.
"""
import json
import logging
import re
from typing import Callable

import requests
from bs4 import BeautifulSoup

from app.parsers.base import BaseSiteParser, ParsedProduct, ScanResult, ScannedItem
from app.parsers.debug import ScanDebugContext
from app.parsers.http import base_url_from, fetch_html, fetch_json
from app.parsers.utils import normalize_url, parse_price_value, selector_config_json

logger = logging.getLogger(__name__)

TILDA_DEFAULT_SELECTORS = {
    "name": "h1.js-product-name",
    "price": ".js-product-price",
    "price_meta": "meta[itemprop='price']",
}

TILDA_DETECT_MARKERS = (
    "data-tilda-project-id",
    "tildacdn.com",
    "t-store",
    "tilda.ws",
    "tilda.cc",
    "/tproduct/",
    "storepart:",
    "js-store",
)

PRODUCT_CARD_SELECTORS = (
    ".t-store__card a[href]",
    ".t-store__card__title a[href]",
    ".js-product a[href]",
    ".t-store__prod-popup a[href]",
    "[class*='t-store'] a[href*='tproduct']",
    "[class*='t-store'] a[href*='product']",
)


class TildaParser(BaseSiteParser):
    """Адаптер для Tilda и Tilda Store."""

    name = "tilda"

    def detect(self, url: str, html: str | None = None) -> bool:
        url_lower = url.lower()
        if any(marker in url_lower for marker in ("tilda.ws", "tilda.cc", "tildacdn.com")):
            return True
        if html:
            html_lower = html.lower()
            return any(marker.lower() in html_lower for marker in TILDA_DETECT_MARKERS)
        return False

    def default_selector_config(self) -> str | None:
        return selector_config_json(TILDA_DEFAULT_SELECTORS)

    def scan_category(
        self, url: str, debug: ScanDebugContext | None = None
    ) -> ScanResult:
        html = fetch_html(url)
        if debug:
            debug.set_html(html)
            debug.url = url

        base = base_url_from(url)
        strategies: list[tuple[str, Callable[[str, str], ScanResult]]] = [
            ("tproduct_links", self._strategy_tproduct_links),
            ("product_cards", self._strategy_product_cards),
            ("json_products", self._strategy_json_products),
            ("schema_org", self._strategy_schema_org),
        ]

        total_rejected = 0
        for strategy_name, strategy_fn in strategies:
            if debug:
                debug.set_strategy(strategy_name)

            result = strategy_fn(html, base)
            total_rejected += result.rejected_links

            if result.items:
                result.strategy = strategy_name
                result.rejected_links = total_rejected
                if debug:
                    debug.set_result([item.url for item in result.items])
                return result

        if debug:
            debug.set_result([])

        return ScanResult(items=[], strategy=None, rejected_links=total_rejected)

    def parse_product(
        self, url: str, selector_config: str | None = None
    ) -> ParsedProduct:
        html = fetch_html(url)
        selectors = self._load_selectors(selector_config)
        soup = BeautifulSoup(html, "html.parser")

        name = ""
        name_el = soup.select_one(selectors["name"])
        if name_el:
            name = name_el.get_text(strip=True)
        if not name:
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                name = og_title["content"].split(" - ")[0].strip()
        if not name:
            schema_name = self._schema_product_field(soup, "name")
            if schema_name:
                name = schema_name

        price: float | None = None
        price_el = soup.select_one(selectors["price"])
        if price_el:
            attr_price = price_el.get("data-product-price-def")
            if attr_price:
                price = parse_price_value(attr_price)
            if price is None:
                price = parse_price_value(price_el.get_text())

        if price is None:
            meta_el = soup.select_one(selectors["price_meta"])
            if meta_el and meta_el.get("content"):
                price = parse_price_value(meta_el["content"])

        if price is None:
            schema_price = self._schema_product_field(soup, "price")
            if schema_price:
                price = parse_price_value(str(schema_price))

        if name and price is not None:
            return ParsedProduct(name=name, price=price)

        fallback = self._parse_from_embedded_product_json(html)
        if fallback:
            return fallback

        raise ValueError("Не удалось извлечь название или цену со страницы")

    def _load_selectors(self, selector_config: str | None) -> dict:
        selectors = TILDA_DEFAULT_SELECTORS.copy()
        if not selector_config:
            return selectors
        try:
            custom = json.loads(selector_config)
            selectors.update(custom)
        except json.JSONDecodeError:
            logger.warning("Некорректный selector_config, используем значения Tilda по умолчанию")
        return selectors

    def _collect_items(
        self,
        candidates: list[tuple[str, str]],
        base: str,
        url_filter: Callable[[str], bool] | None = None,
    ) -> ScanResult:
        seen: set[str] = set()
        items: list[ScannedItem] = []
        rejected = 0

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

        return ScanResult(items=items, rejected_links=rejected)

    def _strategy_tproduct_links(self, html: str, base: str) -> ScanResult:
        soup = BeautifulSoup(html, "html.parser")
        candidates: list[tuple[str, str]] = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "/tproduct/" in href:
                candidates.append((href, link.get_text(strip=True)))
        return self._collect_items(
            candidates, base, url_filter=lambda u: "/tproduct/" in u
        )

    def _strategy_product_cards(self, html: str, base: str) -> ScanResult:
        soup = BeautifulSoup(html, "html.parser")
        candidates: list[tuple[str, str]] = []

        for selector in PRODUCT_CARD_SELECTORS:
            for el in soup.select(selector):
                href = el.get("href", "")
                name = el.get_text(strip=True)
                if href:
                    candidates.append((href, name))

        for card in soup.select("[class*='t-store'], [class*='js-product']"):
            link = card.find("a", href=True)
            if not link:
                continue
            href = link["href"]
            if "/tproduct/" in href or "product" in href.lower():
                title_el = card.select_one(
                    ".t-store__card__title, .js-product-name, .t-name, h2, h3"
                )
                name = title_el.get_text(strip=True) if title_el else link.get_text(strip=True)
                candidates.append((href, name))

        return self._collect_items(
            candidates,
            base,
            url_filter=lambda u: "/tproduct/" in u or "product" in u.lower(),
        )

    def _strategy_json_products(self, html: str, base: str) -> ScanResult:
        items: list[ScannedItem] = []
        rejected = 0
        seen: set[str] = set()

        api_items, api_rejected = self._fetch_store_api_products(html)
        rejected += api_rejected
        for item in api_items:
            if item.url in seen:
                rejected += 1
                continue
            seen.add(item.url)
            items.append(item)

        if items:
            return ScanResult(items=items, rejected_links=rejected)

        for product in self._extract_products_from_scripts(html, base):
            if product.url in seen:
                rejected += 1
                continue
            seen.add(product.url)
            items.append(product)

        return ScanResult(items=items, rejected_links=rejected)

    def _strategy_schema_org(self, html: str, base: str) -> ScanResult:
        soup = BeautifulSoup(html, "html.parser")
        candidates: list[tuple[str, str]] = []

        for script in soup.find_all("script", type="application/ld+json"):
            raw = script.string or script.get_text()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            for node in self._iter_schema_nodes(data):
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

        return self._collect_items(candidates, base)

    def _fetch_store_api_products(self, html: str) -> tuple[list[ScannedItem], int]:
        params = self._extract_store_api_params(html)
        if not params:
            return [], 0

        storepart, recid, project_id = params
        api_url = (
            "https://store.tildacdn.com/api/getproductslist/"
            f"?storepartuid={storepart}&recid={recid}&c={project_id}"
        )
        try:
            data = fetch_json(api_url)
        except (requests.RequestException, ValueError) as exc:
            logger.warning("API Tilda Store недоступен: %s", exc)
            return [], 0

        items: list[ScannedItem] = []
        rejected = 0
        for product in data.get("products", []):
            name = (product.get("title") or "").strip()
            url = (product.get("url") or "").strip()
            if name and url:
                items.append(ScannedItem(name=name, url=url))
            else:
                rejected += 1
        return items, rejected

    def _extract_store_api_params(self, html: str) -> tuple[str, str, str] | None:
        storepart = re.search(r"storepart:\s*['\"](\d+)['\"]", html)
        recid = re.search(r"recid:\s*['\"](\d+)['\"]", html)
        project = re.search(r'data-tilda-project-id=["\'](\d+)["\']', html)
        if storepart and recid:
            project_id = project.group(1) if project else ""
            return storepart.group(1), recid.group(1), project_id
        return None

    def _extract_products_from_scripts(self, html: str, base: str) -> list[ScannedItem]:
        items: list[ScannedItem] = []
        patterns = (
            r'"products"\s*:\s*(\[[\s\S]*?\])\s*[,}]',
            r"var\s+products\s*=\s*(\[[\s\S]*?\]);",
            r"window\.tStoreProducts\s*=\s*(\[[\s\S]*?\]);",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, html):
                try:
                    products = json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
                if not isinstance(products, list):
                    continue
                for product in products:
                    if not isinstance(product, dict):
                        continue
                    name = (product.get("title") or product.get("name") or "").strip()
                    url = (product.get("url") or product.get("link") or "").strip()
                    if url and not url.startswith("http"):
                        url = normalize_url(url, base)
                    if name and url:
                        items.append(ScannedItem(name=name, url=url))
        return items

    def _parse_from_embedded_product_json(self, html: str) -> ParsedProduct | None:
        match = re.search(r"var\s+product\s*=\s*(\{.*?\});", html, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(1))
            name = (data.get("title") or "").strip()
            price = parse_price_value(str(data.get("price", "")))
            if name and price is not None:
                return ParsedProduct(name=name, price=price)
        except (json.JSONDecodeError, TypeError):
            pass
        return None

    def _schema_product_field(self, soup: BeautifulSoup, field: str) -> str | None:
        for script in soup.find_all("script", type="application/ld+json"):
            raw = script.string or script.get_text()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            for node in self._iter_schema_nodes(data):
                if node.get("@type") == "Product" and field in node:
                    return str(node[field])
        return None

    def _iter_schema_nodes(self, data):
        if isinstance(data, list):
            for item in data:
                yield from self._iter_schema_nodes(item)
        elif isinstance(data, dict):
            yield data
            graph = data.get("@graph")
            if isinstance(graph, list):
                yield from self._iter_schema_nodes(graph)
