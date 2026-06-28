"""
Парсеры сайтов конкурентов (адаптеры под CMS).
"""
from app.parsers.base import BaseSiteParser, ParsedProduct, ScanResult, ScannedItem
from app.parsers.registry import get_parser_for_url, list_parsers

__all__ = [
    "BaseSiteParser",
    "ParsedProduct",
    "ScanResult",
    "ScannedItem",
    "get_parser_for_url",
    "list_parsers",
]
