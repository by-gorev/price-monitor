"""
Кэш определения CMS по домену (в памяти процесса).
"""
from urllib.parse import urlparse

_DOMAIN_PARSER: dict[str, str] = {}
_DOMAIN_PLATFORM: dict[str, str] = {}
_DETECT_FAILED: set[str] = set()

_PRODUCT_URL_MARKERS = (
    "/tproduct/",
    "/product/",
    "/products/",
    "/tovar/",
    "route=product",
    "/catalog/",
    "/item/",
)


def get_domain(url: str) -> str:
    """Нормализованный домен (без www.)."""
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def is_product_url(url: str) -> bool:
    """Эвристика: URL страницы товара (detect для него не выполняется)."""
    lower = url.lower()
    path = urlparse(url).path.lower()
    if any(marker in lower for marker in _PRODUCT_URL_MARKERS):
        if path.count("/") >= 2 or "/tproduct/" in lower or "route=product" in lower:
            return True
    return False


def homepage_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"


def get_cached_parser_name(domain: str) -> str | None:
    return _DOMAIN_PARSER.get(domain)


def get_cached_platform(domain: str) -> str | None:
    return _DOMAIN_PLATFORM.get(domain)


def is_detect_failed(domain: str) -> bool:
    return domain in _DETECT_FAILED


def cache_parser(domain: str, parser_name: str, platform: str) -> None:
    _DOMAIN_PARSER[domain] = parser_name
    _DOMAIN_PLATFORM[domain] = platform


def mark_detect_failed(domain: str) -> None:
    _DETECT_FAILED.add(domain)
    cache_parser(domain, "unknown", "Unknown")
