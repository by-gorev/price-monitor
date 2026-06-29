"""
Отладочный вывод при сканировании категорий.
"""
import logging
from pathlib import Path

from app.parsers.parser_types import ParserRunResult, StrategyResult

logger = logging.getLogger(__name__)

DEBUG_DIR = Path(__file__).resolve().parent.parent.parent
DEBUG_HTML_PATH = DEBUG_DIR / "debug_last_page.html"
DEBUG_LINKS_PATH = DEBUG_DIR / "debug_last_links.txt"


class ScanDebugContext:
    """Собирает и выводит отладочную информацию сканирования."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.platform: str | None = None
        self.adapter: str | None = None
        self.strategy: str | None = None
        self.confidence: float | None = None
        self.found_count: int = 0
        self.unique_count: int = 0
        self.raw_candidates: int = 0
        self.rejected_links: int = 0
        self.prices_found: int = 0
        self.without_price: int = 0
        self.sample_urls: list[str] = []
        self.all_links: list[str] = []
        self.url: str | None = None
        self.last_html: str | None = None
        self.stage: str | None = None
        self.elapsed_ms: float | None = None
        self.messages: list[str] = []
        self.strategy_attempts: list[StrategyResult] = []
        self.parser_attempts: list[ParserRunResult] = []

    def set_platform(self, name: str) -> None:
        self.platform = name
        self._log(f"Платформа: {name}")

    def set_adapter(self, name: str) -> None:
        self.adapter = name
        self._log(f"Parser: {name}")

    def set_strategy(self, name: str) -> None:
        self.strategy = name
        self._log(f"Стратегия: {name}")

    def set_confidence(self, value: float) -> None:
        self.confidence = value
        self._log(f"Confidence: {value}")

    def set_stage(self, stage: str) -> None:
        self.stage = stage
        self._log(f"Этап завершения: {stage}")

    def set_elapsed(self, seconds: float) -> None:
        self.elapsed_ms = round(seconds * 1000, 1)
        self._log(f"Время выполнения: {self.elapsed_ms} мс")

    def set_all_links(self, links: list[str]) -> None:
        self.all_links = links

    def set_strategy_attempts(self, attempts: list[StrategyResult]) -> None:
        self.strategy_attempts = attempts

    def record_parser_attempts(self, runs: list[ParserRunResult]) -> None:
        self.parser_attempts = runs
        if not self.enabled:
            return
        for run in runs:
            self._log(
                f"  Parser {run.parser_name}: confidence={run.confidence}, "
                f"товаров={run.products_found}, стратегия={run.strategy_name}"
            )
            for attempt in run.strategy_attempts:
                self._log(
                    f"    → {attempt.strategy_name}: conf={attempt.confidence}, "
                    f"n={attempt.products_found}, prices={attempt.prices_found}"
                    + (f", err={attempt.error}" if attempt.error else "")
                )

    def set_scan_stats(
        self,
        found: int,
        unique: int,
        raw: int,
        rejected: int,
        urls: list[str],
        prices_found: int = 0,
        without_price: int = 0,
    ) -> None:
        self.found_count = found
        self.unique_count = unique
        self.raw_candidates = raw
        self.rejected_links = rejected
        self.prices_found = prices_found
        self.without_price = without_price
        self.sample_urls = urls[:10]

    def set_html(self, html: str) -> None:
        self.last_html = html

    def set_result(self, urls: list[str]) -> None:
        self.set_scan_stats(
            found=len(urls),
            unique=len(urls),
            raw=len(urls),
            rejected=self.rejected_links,
            urls=urls,
        )

    def add_rejected(self, count: int = 1) -> None:
        self.rejected_links += count

    def _log(self, message: str) -> None:
        if not self.enabled:
            return
        self.messages.append(message)
        print(f"[SCAN DEBUG] {message}")
        logger.info("[SCAN DEBUG] %s", message)

    def finish(self, items_found: int) -> None:
        if not self.enabled:
            return

        self._log(f"Найдено товаров: {items_found}")
        self._log(f"Уникальных: {self.unique_count or items_found}")
        self._log(f"С ценой: {self.prices_found}")
        self._log(f"Без цены: {self.without_price}")
        self._log(f"Отброшено ссылок: {self.rejected_links}")

        if self.sample_urls:
            self._log("Первые URL:")
            for sample_url in self.sample_urls:
                self._log(f"  - {sample_url}")

        if items_found == 0:
            if self.last_html:
                DEBUG_HTML_PATH.write_text(self.last_html, encoding="utf-8")
                self._log(f"HTML сохранён: {DEBUG_HTML_PATH}")
            if self.all_links:
                DEBUG_LINKS_PATH.write_text(
                    "\n".join(self.all_links), encoding="utf-8"
                )
                self._log(
                    f"Ссылки сохранены ({len(self.all_links)}): {DEBUG_LINKS_PATH}"
                )

        from app.parsers.http import get_http_stats

        stats = get_http_stats()
        self._log(
            f"HTTP stats: category={stats.category_pages_loaded}, "
            f"product={stats.product_pages_loaded}, cached={stats.cached_pages_used}, "
            f"detect={stats.detect_executed}, requests={stats.http_requests}, "
            f"skipped={stats.skipped_requests}"
        )

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "adapter": self.adapter,
            "parser": self.adapter,
            "strategy": self.strategy,
            "confidence": self.confidence,
            "found": self.found_count,
            "unique": self.unique_count,
            "raw_candidates": self.raw_candidates,
            "rejected_links": self.rejected_links,
            "prices_found": self.prices_found,
            "without_price": self.without_price,
            "sample_urls": self.sample_urls,
            "stage": self.stage,
            "elapsed_ms": self.elapsed_ms,
            "summary": {
                "cms": self.platform,
                "parser": self.adapter,
                "strategy": self.strategy,
                "found": self.found_count,
                "unique": self.unique_count,
                "with_price": self.prices_found,
                "without_price": self.without_price,
                "confidence": self.confidence,
            },
        }
