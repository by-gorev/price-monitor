"""
Контекст загруженной страницы для стратегий сканирования.
"""
from collections.abc import Callable

from bs4 import BeautifulSoup

from app.parsers.debug import ScanDebugContext
from app.parsers.http import base_url_from, load_page_html
from app.parsers.parser_types import ScanResult

StrategyFn = Callable[["PageContext"], ScanResult]


class PageContext:
    """Загруженная страница — один HTTP-запрос на URL."""

    def __init__(self, url: str, html: str, base: str):
        self.url = url
        self.html = html
        self.base = base
        self._soup: BeautifulSoup | None = None

    @classmethod
    def load(
        cls,
        url: str,
        debug: ScanDebugContext | None = None,
        page_type: str = "category",
    ) -> "PageContext":
        html = load_page_html(url, debug=debug, page_type=page_type)
        return cls(url=url, html=html, base=base_url_from(url))

    @property
    def soup(self) -> BeautifulSoup:
        if self._soup is None:
            self._soup = BeautifulSoup(self.html, "html.parser")
        return self._soup
