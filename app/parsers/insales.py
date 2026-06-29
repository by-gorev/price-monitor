"""
Парсер InSales.
"""
from app.parsers.platform_base import BasePlatformParser
from app.parsers.product_parse import parse_from_itemprop, parse_from_schema_org
from app.parsers.strategies import (
    embedded_json_products,
    product_card_selectors,
    product_url_patterns,
    schema_org_products,
)

INSALES_SELECTORS = {
    "name": "h1.product-title, h1[itemprop='name']",
    "price": ".product-price, .price, [itemprop='price']",
    "price_meta": "meta[itemprop='price']",
}

INSALES_CARDS = (
    ".product-card a",
    ".catalog-item a",
    ".collection-product a",
    "[class*='product-card'] a",
)


class InSalesParser(BasePlatformParser):
    name = "insales"
    platform = "InSales"
    priority = 30
    default_selectors = INSALES_SELECTORS
    scan_strategies = [
        (
            "product_urls",
            lambda c: product_url_patterns(
                c,
                ("/product/", "/collection/", "/catalog/"),
                path_keywords=("product", "collection"),
            ),
        ),
        (
            "product_cards",
            lambda c: product_card_selectors(
                c,
                INSALES_CARDS,
                url_filter=lambda u: "product" in u.lower() or "collection" in u.lower(),
            ),
        ),
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
            "insales",
            "InSales",
            "assets.insales",
            "insales.ru",
            "myinsales",
        )
