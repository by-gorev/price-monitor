"""
Парсер WordPress + WooCommerce.
"""
from app.parsers.platform_base import BasePlatformParser
from app.parsers.product_parse import parse_from_itemprop, parse_from_schema_org
from app.parsers.strategies import (
    embedded_json_products,
    product_card_selectors,
    product_url_patterns,
    schema_org_products,
)

WOOCOMMERCE_SELECTORS = {
    "name": "h1.product_title",
    "price": "p.price ins .amount, p.price .amount, .summary .price .amount",
    "price_meta": "meta[property='product:price:amount']",
}

WOOCOMMERCE_CARDS = (
    ".woocommerce-loop-product__link",
    ".products .product a.woocommerce-LoopProduct-link",
    "li.product a[href]",
    ".wc-block-grid__product a",
)


class WooCommerceParser(BasePlatformParser):
    name = "woocommerce"
    platform = "WordPress + WooCommerce"
    priority = 20
    default_selectors = WOOCOMMERCE_SELECTORS
    scan_strategies = [
        (
            "product_urls",
            lambda c: product_url_patterns(
                c,
                ("/product/", "?product=", "add-to-cart="),
                path_keywords=("product",),
            ),
        ),
        (
            "product_cards",
            lambda c: product_card_selectors(c, WOOCOMMERCE_CARDS),
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
        if self.html_contains(
            html,
            "woocommerce",
            "wc-block",
            "wp-content/plugins/woocommerce",
            "woocommerce-loop-product",
            "add-to-cart",
        ):
            return True
        from bs4 import BeautifulSoup

        return self.meta_contains(BeautifulSoup(html, "html.parser"), "woocommerce", "wordpress")
