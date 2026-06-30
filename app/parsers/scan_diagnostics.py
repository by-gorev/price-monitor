"""
Диагностика scan_category: воронка ссылок и причины отбраковки.
Не влияет на логику парсинга — только наблюдение.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from app.parsers.utils import normalize_url

if TYPE_CHECKING:
    from app.parsers.parser_types import ScanResult

logger = logging.getLogger(__name__)

REJECT_REASONS = (
    "not_product_url",
    "external_domain",
    "image",
    "javascript",
    "anchor",
    "duplicate",
    "category_url",
    "blacklist",
    "regex_mismatch",
    "parser_rejected",
    "fetch_failed",
    "no_price",
    "other",
)

_BLACKLIST_PARTS = (
    "cart",
    "checkout",
    "login",
    "register",
    "account",
    "policy",
    "contact",
    "about",
    "blog",
    "news",
    "faq",
    "privacy",
    "wishlist",
    "compare",
)

_CATEGORY_PARTS = (
    "/category/",
    "/categories/",
    "/collection/",
    "/collections/",
    "/catalog/",
    "/katalog/",
    "/kategor",
    "product-category",
    "product_cat",
)

_PRODUCT_HINTS = (
    "product",
    "tovar",
    "tproduct",
    "/item/",
    "add-to-cart",
    "/shop/",
    "/goods/",
)


@dataclass
class LinkRecord:
    url: str
    strategy: str
    accepted: bool
    reason: str | None = None


@dataclass
class StrategyFunnel:
    strategy_name: str
    links_found: int = 0
    product_urls: int = 0
    unique: int = 0
    fetched: int = 0
    parsed: int = 0
    returned: int = 0


@dataclass
class ScanFunnel:
    links_found: int = 0
    product_urls: int = 0
    unique: int = 0
    fetched: int = 0
    parsed: int = 0
    returned: int = 0
    loss_stage: str | None = None


class ScanDiagnosticsCollector:
    """Собирает диагностику сканирования категории."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.base_host = urlparse(base_url).netloc.lower().lstrip("www.")
        self.current_strategy: str = ""
        self.link_records: list[LinkRecord] = []
        self.strategy_funnels: list[StrategyFunnel] = []
        self.page_anchor_count: int = 0
        self._seen_urls: set[str] = set()
        self._strategy_seen: dict[str, set[str]] = {}

    def set_page_anchor_count(self, count: int) -> None:
        self.page_anchor_count = count

    def begin_strategy(self, strategy_name: str) -> None:
        self.current_strategy = strategy_name
        self._strategy_seen.setdefault(strategy_name, set())

    def _record(self, url: str, accepted: bool, reason: str | None = None) -> None:
        self.link_records.append(
            LinkRecord(
                url=url,
                strategy=self.current_strategy or "—",
                accepted=accepted,
                reason=reason,
            )
        )

    def record_accept(self, url: str) -> None:
        self._record(url, True, None)

    def record_reject(self, href: str, reason: str) -> None:
        self._record(href, False, reason)

    def classify_href(self, href: str) -> tuple[str | None, str | None]:
        """
        Классифицировать ссылку. Возвращает (normalized_url, reject_reason).
        reject_reason=None если ссылка выглядит как потенциальный товар.
        """
        raw = (href or "").strip()
        lower = raw.lower()

        if not raw:
            return None, "other"
        if lower.startswith("#"):
            return None, "anchor"
        if lower.startswith("javascript:"):
            return None, "javascript"
        if lower.startswith("mailto:") or lower.startswith("tel:"):
            return None, "other"
        if any(lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg")):
            return None, "image"

        normalized = normalize_url(raw, self.base_url)
        if not normalized:
            return None, "other"

        parsed = urlparse(normalized)
        host = parsed.netloc.lower().lstrip("www.")
        if host and host != self.base_host:
            return None, "external_domain"

        path_lower = parsed.path.lower()
        if any(part in path_lower for part in _BLACKLIST_PARTS):
            return None, "blacklist"
        if any(part in path_lower or part in lower for part in _CATEGORY_PARTS):
            if not any(hint in path_lower for hint in _PRODUCT_HINTS):
                return None, "category_url"

        if not any(hint in path_lower for hint in _PRODUCT_HINTS):
            return None, "not_product_url"

        return normalized, None

    def trace_collect_reject(self, href: str, reason: str) -> None:
        self.record_reject(href, reason)

    def trace_collect_accept(self, url: str) -> None:
        self.record_accept(url)

    def finish_strategy(
        self,
        strategy_name: str,
        result: ScanResult,
        fetched: int = 0,
    ) -> StrategyFunnel:
        """Зафиксировать воронку после выполнения стратегии (без изменения result)."""
        parsed = len(result.items)
        with_price = sum(1 for i in result.items if i.price is not None)
        unique = parsed + max(0, result.rejected_links)

        funnel = StrategyFunnel(
            strategy_name=strategy_name,
            links_found=self.page_anchor_count,
            product_urls=result.raw_candidates,
            unique=unique,
            fetched=fetched,
            parsed=parsed,
            returned=parsed,
        )
        self.strategy_funnels.append(funnel)

        logger.info(
            "[SCAN STRATEGY] %s: links=%s product_urls=%s unique=%s "
            "fetched=%s parsed=%s returned=%s (with_price=%s rejected=%s)",
            strategy_name,
            funnel.links_found,
            funnel.product_urls,
            funnel.unique,
            funnel.fetched,
            funnel.parsed,
            funnel.returned,
            with_price,
            result.rejected_links,
        )
        if funnel.fetched == 0 and funnel.parsed > 0:
            note = (
                "[SCAN STRATEGY] fetched=0 during category scan is expected; "
                "product HTTP runs in price-update phase — see [FETCH DIAG] / debug_last_fetch.txt"
            )
            logger.info(note)
            print(note)
        return funnel

    def build_final_funnel(self, returned: int, best: StrategyFunnel | None) -> ScanFunnel:
        funnel = ScanFunnel(
            links_found=self.page_anchor_count,
            product_urls=best.product_urls if best else 0,
            unique=best.unique if best else 0,
            fetched=best.fetched if best else 0,
            parsed=best.parsed if best else 0,
            returned=returned,
        )
        funnel.loss_stage = self._detect_loss_stage(funnel)
        return funnel

    def _detect_loss_stage(self, funnel: ScanFunnel) -> str | None:
        if funnel.returned > 0:
            return None
        if funnel.links_found == 0:
            return "no_anchor_links"
        if funnel.product_urls == 0:
            return "product_url_filter"
        if funnel.unique == 0:
            return "deduplication_or_name_filter"
        if funnel.parsed == 0:
            return "parser_rejected"
        return "strategy_selection"

    def accepted_urls(self, limit: int = 20) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for rec in self.link_records:
            if rec.accepted and rec.url not in seen:
                seen.add(rec.url)
                out.append(rec.url)
                if len(out) >= limit:
                    break
        return out

    def rejected_urls(self, limit: int = 20) -> list[tuple[str, str]]:
        seen: set[str] = set()
        out: list[tuple[str, str]] = []
        for rec in self.link_records:
            if rec.accepted or not rec.reason:
                continue
            key = f"{rec.url}|{rec.reason}"
            if key in seen:
                continue
            seen.add(key)
            out.append((rec.url, rec.reason))
            if len(out) >= limit:
                break
        return out

    def format_funnel_lines(self, funnel: ScanFunnel) -> list[str]:
        return [
            f"Found links: {funnel.links_found}",
            f"Product URLs: {funnel.product_urls}",
            f"Unique: {funnel.unique}",
            f"Fetched: {funnel.fetched}",
            f"Parsed: {funnel.parsed}",
            f"Returned: {funnel.returned}",
        ]

    def write_links_file(self, path) -> None:
        lines = ["URL\tStrategy\tAccepted\tReason"]
        for rec in self.link_records:
            accepted = "yes" if rec.accepted else "no"
            reason = rec.reason or ""
            lines.append(f"{rec.url}\t{rec.strategy}\t{accepted}\t{reason}")
        path.write_text("\n".join(lines), encoding="utf-8")

    def log_summary(self, items_returned: int, scan_error: str | None = None) -> None:
        best = None
        if self.strategy_funnels:
            best = max(self.strategy_funnels, key=lambda f: f.returned)

        final = self.build_final_funnel(items_returned, best)
        block = self.format_funnel_lines(final)
        for line in block:
            logger.info("[SCAN FUNNEL] %s", line)
            print(f"[SCAN FUNNEL] {line}")

        if scan_error:
            logger.error("Category scan failed: %s", scan_error)
            print(f"[SCAN ERROR] Category scan failed: {scan_error}")

        if items_returned == 0 and self.page_anchor_count > 20:
            msg = "WARNING: Links detected but all rejected after filtering."
            logger.warning(msg)
            print(f"[SCAN WARNING] {msg}")
            if final.loss_stage:
                print(f"[SCAN WARNING] Loss stage: {final.loss_stage}")

            accepted = self.accepted_urls(20)
            rejected = self.rejected_urls(20)
            if accepted:
                print("[SCAN WARNING] First 20 accepted URLs:")
                for url in accepted:
                    print(f"  + {url}")
            if rejected:
                print("[SCAN WARNING] First 20 rejected URLs:")
                for url, reason in rejected:
                    print(f"  - {url} ({reason})")


def format_scan_error(exc: Exception) -> str:
    """Человекочитаемое описание ошибки сканирования."""
    import requests

    from app.parsers.http import FetchFatalError

    if isinstance(exc, FetchFatalError):
        if exc.status_code == 403:
            return "HTTP 403"
        if exc.status_code == 404:
            return "HTTP 404"
        if exc.status_code == 401:
            return "HTTP 401"
        if exc.status_code == 429:
            return "HTTP 429"
        if exc.status_code and exc.status_code >= 500:
            return f"HTTP {exc.status_code}"
        msg = str(exc).lower()
        if "timeout" in msg:
            return "timeout"
        return str(exc) or "fetch_failed"

    if isinstance(exc, requests.Timeout):
        return "timeout"
    if isinstance(exc, requests.ConnectTimeout):
        return "ConnectTimeout"
    if isinstance(exc, requests.ReadTimeout):
        return "ReadTimeout"
    if isinstance(exc, requests.ConnectionError):
        return "ConnectionError"
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        code = exc.response.status_code
        if code == 403:
            return "HTTP 403"
        if code == 404:
            return "HTTP 404"
        if code == 429:
            return "HTTP 429"
        if code >= 500:
            return f"HTTP {code}"
    return str(exc) or "other"
