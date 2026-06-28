"""
HTTP-утилиты для загрузки страниц.
"""
import time
from urllib.parse import urlparse

import requests

from app.config import REQUEST_DELAY_SECONDS

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


def fetch_html(url: str, referer: str | None = None) -> str:
    """Загрузить HTML страницы с задержкой между запросами."""
    time.sleep(REQUEST_DELAY_SECONDS)
    headers = REQUEST_HEADERS.copy()
    if referer:
        headers["Referer"] = referer
    else:
        parsed = urlparse(url)
        headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def fetch_json(url: str, referer: str | None = None) -> dict:
    """Загрузить JSON-ответ API."""
    time.sleep(REQUEST_DELAY_SECONDS)
    headers = REQUEST_HEADERS.copy()
    if referer:
        headers["Referer"] = referer

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def base_url_from(url: str) -> str:
    """Базовый URL сайта (scheme + host)."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"
