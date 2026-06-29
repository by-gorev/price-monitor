"""
Парсер OpenCart.
"""
from app.parsers.platform_base import BasePlatformParser
from app.parsers.product_parse import parse_from_itemprop, parse_from_schema_org
from app.parsers.strategies import (
    embedded_json_products,
    product_card_selectors,
    product_url_patterns,
    schema_org_products,
)

OPENCART_SELECTORS = {
    "name": "h1, .product-info h1",
    "price": ".price-new, .price .price-new, #product .price",
    "price_meta": "meta[itemprop='price']",
}

OPENCART_CARDS = (
    ".product-thumb a",
    ".product-layout a",
    ".product-grid .caption a",
    ".product-item a",
)


class OpenCartParser(BasePlatformParser):
    name = "opencart"
    platform = "OpenCart"
    priority = 35
    default_selectors = OPENCART_SELECTORS
    scan_strategies = [
        (
            "product_urls",
            lambda c: product_url_patterns(
                c,
                ("route=product/product", "/product/", "product_id="),
                path_keywords=("product",),
            ),
        ),
        (
            "product_cards",
            lambda c: product_card_selectors(
                c,
                OPENCART_CARDS,
                url_filter=lambda u: "product" in u.lower(),
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
            "route=product/",
            "catalog/view/theme",
            "index.php?route=product",
            "product-thumb",
            "ocstore",
            "opencart",
        )
