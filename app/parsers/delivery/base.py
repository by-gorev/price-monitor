"""
Базовые классы парсеров доставки.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DeliveryInfo:
    """Результат парсинга условий доставки."""

    price: float | None
    description: str | None
    confidence: float = 0.0


class BaseDeliveryParser(ABC):
    """Базовый адаптер парсинга доставки для CMS."""

    name: str = "base"
    platform: str = "Unknown"
    priority: int = 50

    @abstractmethod
    def detect(self, url: str, html: str | None = None) -> bool:
        """Определить, подходит ли адаптер для сайта."""

    @abstractmethod
    def parse_delivery(self, url: str) -> DeliveryInfo:
        """Извлечь условия и цену доставки."""


class DeliveryParserRegistry:
    """
    Реестр парсеров доставки.
    Регистрация: TildaDeliveryParser, WooCommerceDeliveryParser, ...
    """

    def __init__(self) -> None:
        self._parsers: list[BaseDeliveryParser] = []
        self._fallback: BaseDeliveryParser | None = None

    def register(self, parser: BaseDeliveryParser) -> None:
        self._parsers.append(parser)
        self._parsers.sort(key=lambda p: p.priority)

    def register_fallback(self, parser: BaseDeliveryParser) -> None:
        self._fallback = parser

    def list_parsers(self) -> list[BaseDeliveryParser]:
        return list(self._parsers)

    def get_parser_for_url(
        self, url: str, html: str | None = None
    ) -> BaseDeliveryParser | None:
        for parser in self._parsers:
            if parser.detect(url, html):
                return parser
        return self._fallback


delivery_registry = DeliveryParserRegistry()
