"""
Утилиты для работы с HTML и schema.org (без зависимостей от парсеров).
"""
from typing import Any

from bs4 import BeautifulSoup

from app.parsers.utils import normalize_url


def extract_all_page_links(soup: BeautifulSoup, base: str) -> list[str]:
    """Все абсолютные ссылки со страницы (для debug)."""
    links: list[str] = []
    seen: set[str] = set()
    for tag in soup.find_all("a", href=True):
        normalized = normalize_url(tag["href"], base)
        if normalized and normalized not in seen:
            seen.add(normalized)
            links.append(normalized)
    return links


def iter_schema_nodes(data: Any):
    """Обход узлов JSON-LD (включая @graph)."""
    if isinstance(data, list):
        for item in data:
            yield from iter_schema_nodes(item)
    elif isinstance(data, dict):
        yield data
        graph = data.get("@graph")
        if isinstance(graph, list):
            yield from iter_schema_nodes(graph)
