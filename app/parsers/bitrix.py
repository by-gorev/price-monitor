"""
Парсер 1C-Bitrix.
"""
import re

from app.parsers.page_context import PageContext
from app.parsers.platform_base import BasePlatformParser
from app.parsers.parser_types import ScanResult, ScannedItem
from app.parsers.product_parse import parse_from_itemprop, parse_from_schema_org
from app.parsers.strategies import (
    embedded_json_products,
    product_card_selectors,
    product_url_patterns,
    schema_org_products,
)
from app.parsers.utils import normalize_url

BITRIX_SELECTORS = {
    "name": "h1, .product-item-detail-title",
    "price": ".product-item-detail-price-current, .price_value",
    "price_meta": "meta[itemprop='price']",
}

BITRIX_CARDS = (
    ".product-item a",
    ".catalog-block-view a",
    ".product-item-container a",
    "[data-entity='items-row'] a",
)


def _bitrix_js_catalog(ctx: PageContext) -> ScanResult:
    """Поиск JCCatalogItem / BX в JavaScript."""
    items: list[ScannedItem] = []
    rejected = 0
    raw = 0
    seen: set[str] = set()

    patterns = (
        r'"NAME"\s*:\s*"([^"]+)".*?"DETAIL_PAGE_URL"\s*:\s*"([^"]+)"',
        r'"name"\s*:\s*"([^"]+)".*?"url"\s*:\s*"([^"]+)"',
    )
    for pattern in patterns:
        for match in re.finditer(pattern, ctx.html, re.DOTALL):
            raw += 1
            name = match.group(1).strip()
            href = match.group(2).strip()
            url = normalize_url(href, ctx.base)
            if not name or not url:
                rejected += 1
                continue
            if url in seen:
                rejected += 1
                continue
            seen.add(url)
            items.append(ScannedItem(name=name, url=url))

    return ScanResult(items=items, rejected_links=rejected, raw_candidates=raw)


class BitrixParser(BasePlatformParser):
    name = "bitrix"
    platform = "1C-Bitrix"
    priority = 40
    default_selectors = BITRIX_SELECTORS
    scan_strategies = [
        (
            "product_urls",
            lambda c: product_url_patterns(
                c,
                ("/catalog/", "/product/", "?ELEMENT_ID=", "/bitrix/"),
                path_keywords=("catalog", "product"),
            ),
        ),
        (
            "product_cards",
            lambda c: product_card_selectors(
                c,
                BITRIX_CARDS,
                url_filter=lambda u: "catalog" in u.lower() or "product" in u.lower(),
            ),
        ),
        ("js_catalog", _bitrix_js_catalog),
        ("schema_org", schema_org_products),
        ("embedded_json", embedded_json_products),
    ]
    parse_strategies = [
        ("schema_org", parse_from_schema_org),
        ("itemprop", parse_from_itemprop),
    ]

    def detect(self, url: str, html: str | None = None) -> bool:
        if not html:
            return False
        return self.html_contains(
            html,
            "bitrix",
            "/bitrix/",
            "BX.",
            "JCCatalogItem",
            "bitrix_sessid",
            "1c-bitrix",
        )
