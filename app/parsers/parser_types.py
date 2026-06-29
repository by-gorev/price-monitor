"""
Общие типы данных парсеров (без зависимостей от других модулей parsers).
"""
from dataclasses import dataclass, field


@dataclass
class ScannedItem:
    """Товар, найденный при сканировании категории."""

    name: str
    url: str
    price: float | None = None


@dataclass
class StrategyResult:
    """Результат одной стратегии сканирования."""

    strategy_name: str
    success: bool = False
    confidence: float = 0.0
    products_found: int = 0
    items: list[ScannedItem] = field(default_factory=list)
    links_count: int = 0
    names_found: int = 0
    prices_found: int = 0
    rejected_links: int = 0
    raw_candidates: int = 0
    elapsed_ms: float = 0.0
    error: str | None = None

    @property
    def acceptable(self) -> bool:
        """Стратегия считается успешной для автопереключения."""
        if self.products_found < 3:
            return False
        if self.links_count < self.products_found:
            return False
        if self.names_found < self.products_found:
            return False
        return self.success


@dataclass
class ParserRunResult:
    """Результат запуска одного Parser."""

    parser_name: str
    platform: str
    success: bool = False
    confidence: float = 0.0
    products_found: int = 0
    strategy_name: str | None = None
    items: list[ScannedItem] = field(default_factory=list)
    strategy_attempts: list[StrategyResult] = field(default_factory=list)
    prices_found: int = 0
    without_price: int = 0
    unique_count: int = 0
    rejected_links: int = 0
    elapsed_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
    cms_detected: bool = False


@dataclass
class ScanResult:
    """Итоговый результат сканирования (лучший Parser + стратегия)."""

    items: list[ScannedItem] = field(default_factory=list)
    strategy: str | None = None
    parser_name: str | None = None
    platform: str | None = None
    confidence: float = 0.0
    rejected_links: int = 0
    raw_candidates: int = 0
    prices_found: int = 0
    without_price: int = 0
    parser_attempts: list = field(default_factory=list)
    strategy_attempts: list = field(default_factory=list)


@dataclass
class ParsedProduct:
    """Результат парсинга страницы товара."""

    name: str
    price: float
