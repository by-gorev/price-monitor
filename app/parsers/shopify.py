"""
Парсер Shopify.
"""
from app.parsers.platform_base import BasePlatformParser
from app.parsers.product_parse import parse_from_schema_org
from app.parsers.strategies import (
    collection_products_json,
    product_card_selectors,
    product_url_patterns,
    schema_org_products,
)

SHOPIFY_SELECTORS = {
    "name": "h1.product__title, h1[class*='product-title']",
    "price": ".price__regular .price-item, .product__price .money, [data-product-price]",
    "price_meta": "meta[property='og:price:amount']",
}

SHOPIFY_CARDS = (
    ".product-card a",
    ".grid__item .card-wrapper a",
    ".product-item a",
    "[class*='product-card'] a",
)


class ShopifyParser(BasePlatformParser):
    name = "shopify"
    platform = "Shopify"
    priority = 25
    default_selectors = SHOPIFY_SELECTORS
    scan_strategies = [
        ("product_urls", lambda c: product_url_patterns(c, ("/products/",))),
        (
            "product_cards",
            lambda c: product_card_selectors(
                c,
                SHOPIFY_CARDS,
                url_filter=lambda u: "/products/" in u,
            ),
        ),
        ("products_json", collection_products_json),
        ("schema_org", schema_org_products),
    ]
    parse_strategies = [
        ("schema_org", parse_from_schema_org),
    ]

    def detect(self, url: str, html: str | None = None) -> bool:
        if not html:
            return False
        if self.html_contains(
            html,
            "cdn.shopify.com",
            "shopify-section",
            "Shopify.theme",
            "shopify-features",
            "/products/",
            "myshopify.com",
        ):
            return True
        from bs4 import BeautifulSoup

        return self.meta_contains(BeautifulSoup(html, "html.parser"), "shopify")
