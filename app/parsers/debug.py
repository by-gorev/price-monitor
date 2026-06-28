"""
Отладочный вывод при сканировании категорий.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEBUG_HTML_PATH = Path(__file__).resolve().parent.parent.parent / "debug_last_page.html"


class ScanDebugContext:
    """Собирает и выводит отладочную информацию сканирования."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.adapter: str | None = None
        self.strategy: str | None = None
        self.found_count: int = 0
        self.rejected_links: int = 0
        self.sample_urls: list[str] = []
        self.url: str | None = None
        self.last_html: str | None = None
        self.messages: list[str] = []

    def set_adapter(self, name: str) -> None:
        self.adapter = name
        self._log(f"Адаптер: {name}")

    def set_strategy(self, name: str) -> None:
        self.strategy = name
        self._log(f"Стратегия: {name}")

    def add_rejected(self, count: int = 1) -> None:
        self.rejected_links += count

    def set_result(self, urls: list[str]) -> None:
        self.found_count = len(urls)
        self.sample_urls = urls[:10]

    def set_html(self, html: str) -> None:
        self.last_html = html

    def _log(self, message: str) -> None:
        if not self.enabled:
            return
        self.messages.append(message)
        print(f"[SCAN DEBUG] {message}")
        logger.info("[SCAN DEBUG] %s", message)

    def finish(self, items_found: int) -> None:
        """Вывести итоговую сводку и при необходимости сохранить HTML."""
        if not self.enabled:
            return

        self._log(f"Найдено товаров: {items_found}")
        self._log(f"Отброшено ссылок: {self.rejected_links}")

        if self.sample_urls:
            self._log("Первые URL:")
            for sample_url in self.sample_urls:
                self._log(f"  - {sample_url}")

        if items_found == 0 and self.last_html:
            DEBUG_HTML_PATH.write_text(self.last_html, encoding="utf-8")
            self._log(f"HTML сохранён: {DEBUG_HTML_PATH}")

    def to_dict(self) -> dict:
        return {
            "adapter": self.adapter,
            "strategy": self.strategy,
            "found": self.found_count,
            "rejected_links": self.rejected_links,
            "sample_urls": self.sample_urls,
        }
