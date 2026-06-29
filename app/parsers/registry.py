"""
Реестр парсеров — определение CMS по домену (один раз) и оркестратор.
"""
import logging

from app.parsers.base import BaseSiteParser
from app.parsers.bitrix import BitrixParser
from app.parsers.debug import ScanDebugContext
from app.parsers.domain_cache import (
    cache_parser,
    get_cached_parser_name,
    get_cached_platform,
    get_domain,
    homepage_url,
    is_detect_failed,
    is_product_url,
    mark_detect_failed,
)
from app.parsers.fallback import FallbackParser
from app.parsers.http import FetchFatalError, get_http_stats, load_page_html
from app.parsers.insales import InSalesParser
from app.parsers.opencart import OpenCartParser
from app.parsers.orchestrator import OrchestratedParser
from app.parsers.shopify import ShopifyParser
from app.parsers.tilda import TildaParser
from app.parsers.woocommerce import WooCommerceParser

logger = logging.getLogger(__name__)

_REGISTERED_PARSERS: list[BaseSiteParser] = [
    TildaParser(),
    WooCommerceParser(),
    ShopifyParser(),
    InSalesParser(),
    OpenCartParser(),
    BitrixParser(),
]

_FALLBACK_PARSER = FallbackParser()

_PARSER_BY_NAME: dict[str, BaseSiteParser] = {
    p.name: p for p in _REGISTERED_PARSERS
}
_PARSER_BY_NAME[_FALLBACK_PARSER.name] = _FALLBACK_PARSER


def list_parsers() -> list[BaseSiteParser]:
    return list(_REGISTERED_PARSERS)


def _parser_by_name(name: str) -> BaseSiteParser:
    return _PARSER_BY_NAME.get(name, _FALLBACK_PARSER)


def resolve_parser_for_domain(
    url: str,
    html: str | None = None,
    debug: ScanDebugContext | None = None,
) -> BaseSiteParser:
    """
    Определить Parser для домена (один раз).
    detect() выполняется только для главной или категории, не для товаров.
    """
    domain = get_domain(url)

    if is_detect_failed(domain):
        return _FALLBACK_PARSER

    cached_name = get_cached_parser_name(domain)
    if cached_name:
        return _parser_by_name(cached_name)

    detect_url = url
    page_html = html

    if is_product_url(url):
        detect_url = homepage_url(url)
        page_html = None

    if page_html is None:
        try:
            page_html = load_page_html(detect_url, debug=debug, page_type="detect")
        except FetchFatalError as exc:
            logger.warning("detect прерван для %s: %s", detect_url, exc)
            mark_detect_failed(domain)
            return _FALLBACK_PARSER

    get_http_stats().detect_executed += 1

    for parser in _REGISTERED_PARSERS:
        if parser.detect(detect_url, page_html):
            cache_parser(domain, parser.name, parser.platform)
            return parser

    cache_parser(domain, _FALLBACK_PARSER.name, _FALLBACK_PARSER.platform)
    return _FALLBACK_PARSER


def get_parser_for_url(
    url: str,
    html: str | None = None,
    debug: ScanDebugContext | None = None,
) -> BaseSiteParser:
    """
    Вернуть оркестратор с Parser, закреплённым за доменом.
    Повторный detect() для известного домена не выполняется.
    """
    domain = get_domain(url)
    primary = resolve_parser_for_domain(url, html=html, debug=debug)

    return OrchestratedParser(
        parsers=_REGISTERED_PARSERS,
        fallback=_FALLBACK_PARSER,
        primary=primary,
        domain=domain,
        domain_cached=get_cached_parser_name(domain) is not None,
        platform=get_cached_platform(domain) or primary.platform,
    )
