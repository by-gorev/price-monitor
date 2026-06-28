"""
Реестр парсеров — выбор адаптера по URL без привязки к конкретному конкуренту.
"""
import logging

from app.parsers.base import BaseSiteParser
from app.parsers.debug import ScanDebugContext
from app.parsers.http import fetch_html
from app.parsers.tilda import TildaParser

logger = logging.getLogger(__name__)

# Новые адаптеры регистрируются здесь (WordPress, InSales, OpenCart, Shopify, Bitrix)
_REGISTERED_PARSERS: list[BaseSiteParser] = [
    TildaParser(),
]


def list_parsers() -> list[BaseSiteParser]:
    """Список зарегистрированных адаптеров."""
    return list(_REGISTERED_PARSERS)


def get_parser_for_url(
    url: str,
    html: str | None = None,
    debug: ScanDebugContext | None = None,
) -> BaseSiteParser | None:
    """
    Определить тип сайта и вернуть подходящий адаптер.
    При необходимости загружает HTML для detect().
    """
    page_html = html
    if page_html is None:
        try:
            page_html = fetch_html(url)
            if debug:
                debug.set_html(page_html)
        except Exception as exc:
            logger.warning("Не удалось загрузить страницу для detect(%s): %s", url, exc)
            page_html = ""

    for parser in _REGISTERED_PARSERS:
        if parser.detect(url, page_html):
            if debug:
                debug.set_adapter(parser.name)
            return parser

    if debug:
        debug.set_adapter("не найден")
    return None
