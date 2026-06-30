"""
HTTP-утилиты: сессия, кэш страниц, статистика запросов.
"""
import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests

from app.config import REQUEST_DELAY_SECONDS

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 10
REQUEST_TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

_FATAL_HTTP_CODES = frozenset({401, 403, 404})

# Глобальный кэш HTML по URL (нормализованный ключ)
_PAGE_CACHE: dict[str, str] = {}
# Цены с страницы категории (url → name, price)
_LISTING_ITEMS: dict[str, tuple[str, float]] = {}


class FetchFatalError(requests.RequestException):
    """HTTP-ошибка, при которой detect не продолжается."""

    def __init__(self, url: str, status_code: int | None = None, message: str = ""):
        self.url = url
        self.status_code = status_code
        super().__init__(message or f"Fatal fetch error for {url}")


@dataclass
class HttpStats:
    category_pages_loaded: int = 0
    product_pages_loaded: int = 0
    cached_pages_used: int = 0
    detect_executed: int = 0
    http_requests: int = 0
    skipped_requests: int = 0


@dataclass
class HttpContext:
    """Один requests.Session на операцию сканирования."""

    session: requests.Session = field(default_factory=requests.Session)
    stats: HttpStats = field(default_factory=HttpStats)

    def __post_init__(self) -> None:
        self.session.headers.update(REQUEST_HEADERS)


_http_ctx: ContextVar[HttpContext | None] = ContextVar("http_ctx", default=None)


def _url_key(url: str) -> str:
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc.lower()}{path}"


def begin_http_scan() -> HttpContext:
    """Начать новую HTTP-сессию для сканирования категории."""
    _LISTING_ITEMS.clear()
    ctx = HttpContext()
    _http_ctx.set(ctx)
    return ctx


def get_http_context() -> HttpContext:
    """Текущий HTTP-контекст (создаётся при первом обращении)."""
    ctx = _http_ctx.get()
    if ctx is None:
        ctx = HttpContext()
        _http_ctx.set(ctx)
    return ctx


def get_http_stats() -> HttpStats:
    return get_http_context().stats


def _referer(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    return {"Referer": f"{parsed.scheme}://{parsed.netloc}/"}


def _get_cached(url: str) -> str | None:
    key = _url_key(url)
    html = _PAGE_CACHE.get(key)
    if html is not None:
        get_http_context().stats.cached_pages_used += 1
        get_http_context().stats.skipped_requests += 1
    return html


def _store_cache(url: str, html: str) -> None:
    _PAGE_CACHE[_url_key(url)] = html


def cache_listing_prices(items) -> None:
    """Сохранить цены с листинга — parse_product не откроет страницу товара."""
    for item in items:
        if item.price is not None:
            _LISTING_ITEMS[_url_key(item.url)] = (item.name, item.price)


def get_listing_price(url: str) -> tuple[str, float] | None:
    return _LISTING_ITEMS.get(_url_key(url))


def fetch_html(url: str, referer: str | None = None, page_type: str = "product") -> str:
    """
    Загрузить HTML с кэшем и единой сессией.
    page_type: 'category' | 'product' | 'detect'
    """
    from app.parsers.fetch_diagnostics import get_fetch_diagnostics

    diag = get_fetch_diagnostics()
    if diag:
        diag.before_request(url, page_type)

    cached = _get_cached(url)
    if cached is not None:
        if diag:
            diag.mark_skip(url, "page_cache_hit")
        return cached

    ctx = get_http_context()
    time.sleep(REQUEST_DELAY_SECONDS)

    headers = _referer(referer or url)
    try:
        response = ctx.session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if diag:
            diag.record_response(url, page_type, response.status_code, response.url)
        if response.status_code in _FATAL_HTTP_CODES:
            fatal = FetchFatalError(url, response.status_code, f"HTTP {response.status_code}")
            if diag:
                diag.record_exception(url, page_type, fatal)
            raise fatal
        response.raise_for_status()
    except requests.Timeout as exc:
        if diag:
            diag.record_exception(url, page_type, exc)
        raise FetchFatalError(url, message="timeout") from exc
    except requests.ConnectionError as exc:
        if diag:
            diag.record_exception(url, page_type, exc)
        raise FetchFatalError(url, message="connection error") from exc
    except Exception as exc:
        if diag and not isinstance(exc, FetchFatalError):
            diag.record_exception(url, page_type, exc)
        raise

    response.encoding = response.apparent_encoding or "utf-8"
    html = response.text

    ctx.stats.http_requests += 1
    if page_type == "category":
        ctx.stats.category_pages_loaded += 1
    elif page_type == "product":
        ctx.stats.product_pages_loaded += 1

    _store_cache(url, html)
    return html


def load_page_html(
    url: str,
    debug=None,
    page_type: str = "product",
) -> str:
    """Загрузить HTML с учётом debug-контекста и кэша."""
    from app.parsers.fetch_diagnostics import get_fetch_diagnostics, trace_fetch_skip

    if debug and debug.url == url and debug.last_html:
        get_http_context().stats.cached_pages_used += 1
        get_http_context().stats.skipped_requests += 1
        if page_type == "product":
            trace_fetch_skip(url, "debug_html_reuse")
        return debug.last_html

    diag = get_fetch_diagnostics()
    if diag:
        diag.before_request(url, page_type)

    html = fetch_html(url, page_type=page_type)
    if debug:
        debug.set_html(html)
        debug.url = url
    return html


def fetch_json(url: str, referer: str | None = None) -> dict:
    """Загрузить JSON через текущую сессию."""
    cached = _get_cached(url)
    if cached is not None:
        import json

        return json.loads(cached)

    ctx = get_http_context()
    time.sleep(REQUEST_DELAY_SECONDS)
    headers = _referer(referer or url)
    try:
        response = ctx.session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code in _FATAL_HTTP_CODES:
            raise FetchFatalError(url, response.status_code)
        response.raise_for_status()
    except requests.Timeout as exc:
        raise FetchFatalError(url, message="timeout") from exc

    ctx.stats.http_requests += 1
    data = response.json()
    import json

    _store_cache(url, json.dumps(data, ensure_ascii=False))
    return data


def base_url_from(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def log_http_stats(platform: str | None = None, elapsed_sec: float | None = None) -> None:
    """Вывести статистику HTTP после сканирования."""
    stats = get_http_stats()
    lines = [
        f"Platform: {platform or '—'}",
        f"Category pages loaded: {stats.category_pages_loaded}",
        f"Product pages loaded: {stats.product_pages_loaded}",
        f"Cached pages used: {stats.cached_pages_used}",
        f"Detect executed: {stats.detect_executed}",
        f"HTTP requests: {stats.http_requests}",
        f"Skipped requests: {stats.skipped_requests}",
    ]
    if elapsed_sec is not None:
        lines.append(f"Elapsed: {elapsed_sec:.1f} sec")
    block = "\n".join(lines)
    print(f"[SCAN STATS]\n{block}")
    logger.info("[SCAN STATS]\n%s", block)
