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


def parse_price_value(text: str) -> float | None:
    """Преобразовать строку цены в число."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d,.\-]", "", str(text).strip())
    cleaned = cleaned.replace(",", ".")
    if cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(cleaned)
    except ValueError:
        return None


def selector_config_json(config: dict) -> str:
    """Сериализовать конфиг селекторов для поля selector_config."""
    return json.dumps(config, ensure_ascii=False)
