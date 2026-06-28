"""
Абстрактный интерфейс парсера сайта конкурента.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.parsers.debug import ScanDebugContext


@dataclass
class ScannedItem:
    """Товар, найденный при сканировании категории."""

    name: str
    url: str


@dataclass
class ScanResult:
    """Результат сканирования страницы категории."""

    items: list[ScannedItem] = field(default_factory=list)
    strategy: str | None = None
    rejected_links: int = 0


@dataclass
class ParsedProduct:
    """Результат парсинга страницы товара."""

    name: str
    price: float


class BaseSiteParser(ABC):
    """Базовый адаптер CMS. Каждая реализация инкапсулирует логику одной платформы."""

    name: str = "base"

    @abstractmethod
    def detect(self, url: str, html: str | None = None) -> bool:
        """Определить, подходит ли адаптер для данного URL/страницы."""

    @abstractmethod
    def scan_category(
        self, url: str, debug: ScanDebugContext | None = None
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
