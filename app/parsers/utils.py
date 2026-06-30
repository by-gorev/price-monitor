"""
Общие утилиты парсинга.
"""
import json
import re
from urllib.parse import urljoin, urlparse


def normalize_url(href: str, base: str) -> str:
    """Привести ссылку к абсолютному URL без фрагмента."""
    href = href.strip()
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
        return ""
    absolute = urljoin(base, href)
    parsed = urlparse(absolute)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/") or absolute


def normalize_price(text: str) -> float | None:
    """Преобразовать строку цены в число (первое отдельное значение, без склейки)."""
    if not text:
        return None
    raw = str(text).strip()
    match = re.search(r"(\d+(?:[.,]\d{1,2})?)", raw)
    if not match:
        return None
    num = match.group(1).replace(",", ".")
    try:
        return float(num)
    except ValueError:
        return None


def parse_price_value(text: str) -> float | None:
    """Алиас normalize_price для обратной совместимости."""
    return normalize_price(text)


def selector_config_json(config: dict) -> str:
    """Сериализовать конфиг селекторов для поля selector_config."""
    return json.dumps(config, ensure_ascii=False)
