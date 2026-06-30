"""
Отладочный вывод при сканировании категорий.
"""
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from app.parsers.parser_types import ParserRunResult, StrategyResult

if TYPE_CHECKING:
    from app.parsers.scan_diagnostics import ScanDiagnosticsCollector

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
        self.diagnostics: ScanDiagnosticsCollector | None = None
        self.scan_error: str | None = None
        self.funnel_summary: dict = {}
        self.final_price_stats: dict = {}

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

    def set_scan_error(self, error: str | None) -> None:
        self.scan_error = error
        if error:
            self._log(f"Ошибка сканирования: {error}")

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
                funnel = attempt.funnel or {}
                funnel_line = ""
                if funnel:
                    funnel_line = (
                        f", links={funnel.get('links_found')}, "
                        f"product_urls={funnel.get('product_urls')}, "
                        f"unique={funnel.get('unique')}, "
                        f"parsed={funnel.get('parsed')}, "
                        f"returned={funnel.get('returned')}"
                    )
                self._log(
                    f"    → {attempt.strategy_name}: conf={attempt.confidence}, "
                    f"n={attempt.products_found}, prices={attempt.prices_found}"
                    f"{funnel_line}"
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

    def finish(self, items_found: int, scan_error: str | None = None) -> None:
        if scan_error:
            self.set_scan_error(scan_error)

        if self.diagnostics:
            self.diagnostics.write_links_file(DEBUG_LINKS_PATH)
            self.diagnostics.log_summary(items_found, scan_error or self.scan_error)
            if self.diagnostics.strategy_funnels:
                best = max(self.diagnostics.strategy_funnels, key=lambda f: f.returned)
                final = self.diagnostics.build_final_funnel(items_found, best)
                self.funnel_summary = {
                    "links_found": final.links_found,
                    "product_urls": final.product_urls,
                    "unique": final.unique,
                    "fetched": final.fetched,
                    "parsed": final.parsed,
                    "returned": final.returned,
                    "loss_stage": final.loss_stage,
                }

        if not self.enabled:
            return

        self._log(f"Найдено товаров (скан категории): {items_found}")
        self._log(f"Уникальных: {self.unique_count or items_found}")
        self._log(f"Отброшено ссылок: {self.rejected_links}")

        if self.funnel_summary:
            for key in (
                "links_found",
                "product_urls",
                "unique",
                "fetched",
                "parsed",
                "returned",
            ):
                self._log(f"Funnel {key}: {self.funnel_summary.get(key)}")
            if self.funnel_summary.get("loss_stage"):
                self._log(f"Loss stage: {self.funnel_summary['loss_stage']}")

        if self.sample_urls:
            self._log("Первые URL:")
            for sample_url in self.sample_urls:
                self._log(f"  - {sample_url}")

        if items_found == 0 or self.diagnostics:
            if self.last_html:
                DEBUG_HTML_PATH.write_text(self.last_html, encoding="utf-8")
                self._log(f"HTML сохранён: {DEBUG_HTML_PATH}")
            if self.diagnostics and DEBUG_LINKS_PATH.exists():
                self._log(
                    f"Ссылки сохранены ({len(self.diagnostics.link_records)}): "
                    f"{DEBUG_LINKS_PATH}"
                )
            elif self.all_links:
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
        from app.parsers.fetch_diagnostics import DEBUG_FETCH_PATH

        if DEBUG_FETCH_PATH.exists():
            self._log(f"Fetch diagnostics: {DEBUG_FETCH_PATH}")
        from app.parsers.price_diagnostics import DEBUG_PRICE_PATH

        if DEBUG_PRICE_PATH.exists():
            self._log(f"Price diagnostics: {DEBUG_PRICE_PATH}")

    def finalize_prices(self, found: int, stats: dict) -> None:
        """Итоговая статистика после parse_and_save (не с листинга)."""
        self.found_count = found
        self.final_price_stats = dict(stats)
        self.prices_found = int(stats.get("with_price", 0))
        self.without_price = int(stats.get("without_price", 0))

        if not self.enabled:
            return

        self._log("—— Итог после обновления цен ——")
        self._log(f"Найдено товаров: {found}")
        self._log(f"Успешно сохранено: {stats.get('saved', 0)}")
        self._log(f"Цена получена: {stats.get('with_price', 0)}")
        self._log(f"Без цены: {stats.get('without_price', 0)}")
        self._log(f"Ошибки парсинга: {stats.get('parse_errors', 0)}")
        if stats.get("skipped"):
            self._log(f"Пропущено (не обновлялись): {stats['skipped']}")

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
            "error": self.scan_error,
            "funnel": self.funnel_summary,
            "final_price_stats": self.final_price_stats,
            "summary": {
                "cms": self.platform,
                "parser": self.adapter,
                "strategy": self.strategy,
                "found": self.found_count,
                "unique": self.unique_count,
                "with_price": self.prices_found,
                "without_price": self.without_price,
                "saved": self.final_price_stats.get("saved", 0),
                "parse_errors": self.final_price_stats.get("parse_errors", 0),
                "skipped": self.final_price_stats.get("skipped", 0),
                "confidence": self.confidence,
                "error": self.scan_error,
                "funnel": self.funnel_summary,
            },
        }
