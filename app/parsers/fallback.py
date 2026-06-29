"""
Универсальный парсер (fallback) для неизвестных CMS.
"""
from app.parsers.platform_base import BasePlatformParser
from app.parsers.product_parse import (
    parse_from_embedded_json,
    parse_from_opengraph,
    parse_from_schema_org,
)
from app.parsers.strategies import (
    generic_cms_cards,
    generic_product_like_links,
    schema_org_products,
)


class FallbackParser(BasePlatformParser):
    """
    Используется, когда платформа не определена.
    Пытается извлечь товары максимально универсальными способами.
    """

    name = "unknown"
    platform = "Unknown"
    priority = 999
    scan_strategies = [
        ("schema_org", schema_org_products),
        ("product_like_urls", generic_product_like_links),
        ("cms_cards", generic_cms_cards),
    ]
    parse_strategies = [
        ("schema_org", parse_from_schema_org),
        ("opengraph", parse_from_opengraph),
        ("embedded_json", parse_from_embedded_json),
    ]

    def detect(self, url: str, html: str | None = None) -> bool:
        """Fallback не участвует в автоопределении — выбирается реестром последним."""
        return False
