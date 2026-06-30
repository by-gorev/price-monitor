"""
Извлечение цены со страницы товара: отдельный анализ каждого источника.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString, Tag

from app.parsers.utils import normalize_price

_CURRENCY_MARKERS = ("₽", "руб", "р.", "rub", "$", "€", "eur", "usd")
_DECIMAL_RE = re.compile(r"\d+[.,]\d{1,2}")


@dataclass
class PriceCandidate:
    selector: str
    raw: str
    normalized: float | None


def _selector_parts(selector: str) -> list[str]:
    return [part.strip() for part in selector.split(",") if part.strip()]


def _looks_like_price(raw: str, normalized: float | None, selector: str) -> bool:
    if normalized is None or normalized <= 0:
        return False
    if "<" in raw or ">" in raw:
        return False
    lower = raw.lower()
    if any(marker in lower for marker in _CURRENCY_MARKERS):
        return True
    if _DECIMAL_RE.search(raw):
        return True
    if normalized >= 10:
        return True
    return False


def _attribute_sources(el: Tag) -> list[str]:
    sources: list[str] = []
    for attr in ("content", "data-product-price-def"):
        value = el.get(attr)
        if value:
            sources.append(str(value).strip())
    return sources


def _direct_text_sources(el: Tag) -> list[str]:
    """Текстовые фрагменты без склейки вложенных поддеревьев в одну строку."""
    if not el.find(True):
        text = el.get_text(strip=True)
        return [text] if text else []

    sources: list[str] = []
    for child in el.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                sources.append(text)
        elif isinstance(child, Tag):
            sources.extend(_direct_text_sources(child))
    return sources


def _element_sources(el: Tag) -> list[str]:
    sources = _attribute_sources(el)
    if sources:
        return [s for s in sources if s and "<" not in s]
    return [s for s in _direct_text_sources(el) if s and "<" not in s]


def collect_price_candidates(soup: BeautifulSoup, selectors: dict) -> list[PriceCandidate]:
    """Собрать все кандидаты цены по CSS-селекторам и meta."""
    candidates: list[PriceCandidate] = []

    price_selector = selectors.get("price")
    if price_selector:
        for part in _selector_parts(price_selector):
            for el in soup.select(part):
                for raw in _element_sources(el):
                    candidates.append(
                        PriceCandidate(
                            selector=part,
                            raw=raw,
                            normalized=normalize_price(raw),
                        )
                    )

    meta_selector = selectors.get("price_meta")
    if meta_selector:
        for part in _selector_parts(meta_selector):
            for el in soup.select(part):
                raw = (el.get("content") or el.get_text(strip=True) or "").strip()
                if raw:
                    candidates.append(
                        PriceCandidate(
                            selector=part,
                            raw=raw,
                            normalized=normalize_price(raw),
                        )
                    )

    return candidates


def select_price(candidates: list[PriceCandidate]) -> float | None:
    """Выбрать итоговую цену из кандидатов (без склейки чисел)."""
    for candidate in candidates:
        if _looks_like_price(candidate.raw, candidate.normalized, candidate.selector):
            return candidate.normalized
    for candidate in candidates:
        if candidate.normalized is not None and candidate.normalized > 0:
            return candidate.normalized
    return None
