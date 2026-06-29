"""
Абстрактный интерфейс парсера сайта конкурента.
"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.parsers.parser_types import (
    ParsedProduct,
    ParserRunResult,
    ScanResult,
    ScannedItem,
    StrategyResult,
)

if TYPE_CHECKING:
    from app.parsers.debug import ScanDebugContext

# Обратная совместимость импортов из app.parsers.base
__all__ = [
    "BaseSiteParser",
    "ParsedProduct",
    "ParserRunResult",
    "ScanResult",
    "ScannedItem",
    "StrategyResult",
]


class BaseSiteParser(ABC):
    """Базовый адаптер CMS. Каждая реализация инкапсулирует логику одной платформы."""

    name: str = "base"
    platform: str = "Unknown"
    priority: int = 50

    @abstractmethod
    def detect(self, url: str, html: str | None = None) -> bool:
        """Определить, подходит ли адаптер для данного URL/страницы."""

    @abstractmethod
    def scan_category(
        self, url: str, debug: "ScanDebugContext | None" = None
    ) -> ScanResult:
        """Найти товары на странице категории."""

    @abstractmethod
    def parse_product(
        self, url: str, selector_config: str | None = None
    ) -> ParsedProduct:
        """Распарсить страницу товара (название и цена)."""

    def default_selector_config(self) -> str | None:
        """JSON-конфиг селекторов для новых товаров (если применимо)."""
        return None
