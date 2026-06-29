"""
Парсер Tilda Store.
"""
import re

import requests

from app.parsers.parser_types import ScanResult, ScannedItem
from app.parsers.http import fetch_json
from app.parsers.page_context import PageContext
from app.parsers.platform_base import BasePlatformParser
from app.parsers.product_parse import parse_from_embedded_json, parse_from_schema_org
from app.parsers.strategies import (
    embedded_json_products,
    product_card_selectors,
    product_url_patterns,
    schema_org_products,
)
from app.parsers.utils import parse_price_value

TILDA_SELECTORS = {
    "name": "h1.js-product-name",
    "price": ".js-product-price",
    "price_meta": "meta[itemprop='price']",
}

TILDA_CARD_SELECTORS = (
    ".t-store__card a[href]",
    ".t-store__card__title a[href]",
    ".js-product a[href]",
    ".t-store__prod-popup a[href]",
    "[class*='t-store'] a[href*='tproduct']",
    "[class*='t-store'] [class*='js-product']",
)


def _tilda_api(ctx: PageContext) -> ScanResult:
    storepart = re.search(r"storepart:\s*['\"](\d+)['\"]", ctx.html)
    recid = re.search(r"recid:\s*['\"](\d+)['\"]", ctx.html)
    project = re.search(r'data-tilda-project-id=["\'](\d+)["\']', ctx.html)
    if not (storepart and recid):
        return ScanResult()

    project_id = project.group(1) if project else ""
    api_url = (
        "https://store.tildacdn.com/api/getproductslist/"
        f"?storepartuid={storepart.group(1)}&recid={recid.group(1)}&c={project_id}"
    )
    try:
        data = fetch_json(api_url, referer=ctx.url)
    except (requests.RequestException, ValueError):
        return ScanResult()

    items: list[ScannedItem] = []
    rejected = 0
    for product in data.get("products", []):
        name = (product.get("title") or "").strip()
        url = (product.get("url") or "").strip()
        if name and url:
            price_raw = product.get("price")
            price = parse_price_value(str(price_raw)) if price_raw is not None else None
            items.append(ScannedItem(name=name, url=url, price=price))
        else:
            rejected += 1
    return ScanResult(items=items, rejected_links=rejected, raw_candidates=len(data.get("products", [])))


def _tilda_cards(ctx: PageContext) -> ScanResult:
    return product_card_selectors(
        ctx,
        TILDA_CARD_SELECTORS,
        url_filter=lambda u: "/tproduct/" in u or "product" in u.lower(),
    )


def _tilda_embedded(ctx: PageContext) -> ScanResult:
    return embedded_json_products(
        ctx,
        patterns=(
            r'"products"\s*:\s*(\[[\s\S]*?\])\s*[,}]',
            r"var\s+products\s*=\s*(\[[\s\S]*?\]);",
            r"window\.tStoreProducts\s*=\s*(\[[\s\S]*?\]);",
        ),
    )


class TildaParser(BasePlatformParser):
    name = "tilda"
    platform = "Tilda Store"
    priority = 10
    default_selectors = TILDA_SELECTORS
    scan_strategies = [
        ("tproduct_urls", lambda c: product_url_patterns(c, ("/tproduct/",))),
        ("product_cards", _tilda_cards),
        ("store_api", _tilda_api),
        ("embedded_json", _tilda_embedded),
        ("schema_org", schema_org_products),
    ]
    parse_strategies = [
        ("embedded_json", parse_from_embedded_json),
        ("schema_org", parse_from_schema_org),
    ]

    def detect(self, url: str, html: str | None = None) -> bool:
        if not html:
            return False
        if self.html_contains(
            html,
            "data-tilda-project-id",
            "tildacdn.com",
            "t-store",
            "js-store",
            "storepart:",
            "/tproduct/",
        ):
            return True
        soup_markers = ("tilda", "t-store")
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        return self.meta_contains(soup, *soup_markers)
