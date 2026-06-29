"""
Парсеры сайтов конкурентов (адаптеры под CMS).
"""
from app.parsers.base import (
    BaseSiteParser,
    ParsedProduct,
    ParserRunResult,
    ScanResult,
    ScannedItem,
    StrategyResult,
)
from app.parsers.delivery import BaseDeliveryParser, DeliveryParserRegistry, delivery_registry
from app.parsers.registry import get_parser_for_url, list_parsers

__all__ = [
    "BaseDeliveryParser",
    "BaseSiteParser",
    "DeliveryParserRegistry",
    "ParsedProduct",
    "ParserRunResult",
    "ScanResult",
    "ScannedItem",
    "StrategyResult",
    "delivery_registry",
    "get_parser_for_url",
    "list_parsers",
]
