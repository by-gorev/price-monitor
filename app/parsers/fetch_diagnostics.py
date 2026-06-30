"""
Диагностика этапа fetch (открытие карточек товара).
Только наблюдение — не влияет на HTTP-логику.
"""
from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from app.parsers.utils import normalize_url

logger = logging.getLogger(__name__)

DEBUG_FETCH_PATH = (
    Path(__file__).resolve().parent.parent.parent / "debug_last_fetch.txt"
)

_fetch_diag_ctx: ContextVar[FetchDiagnosticsCollector | None] = ContextVar(
    "fetch_diag_ctx", default=None
)


def cache_url_key(url: str) -> str:
    """Ключ кэша страницы (для диагностики)."""
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc.lower()}{path}"


@dataclass
class FetchTrace:
    index: int
    original_href: str
    normalized_url: str
    cache_key_url: str
    request_url: str
    skipped: bool = False
    skip_reason: str | None = None
    http_status: int | None = None
    redirect_url: str | None = None
    exception: str | None = None


@dataclass
class FetchDiagnosticsCollector:
    base_url: str
    limit: int = 20
    traces: dict[str, FetchTrace] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)
    _logged_pipeline: set[str] = field(default_factory=set)

    def register_product_url(self, href: str) -> None:
        if len(self._order) >= self.limit:
            return
        if not href or not href.strip():
            return

        original = href.strip()
        normalized = normalize_url(original, self.base_url) or original
        if normalized in self.traces:
            return

        trace = FetchTrace(
            index=len(self._order) + 1,
            original_href=original,
            normalized_url=normalized,
            cache_key_url=cache_url_key(normalized),
            request_url=normalized,
        )
        self.traces[normalized] = trace
        self._order.append(normalized)
        self._log_pipeline(trace)

    def _resolve(self, url: str) -> FetchTrace | None:
        if not url:
            return None
        normalized = normalize_url(url, self.base_url) or url.strip()
        if normalized in self.traces:
            return self.traces[normalized]
        key = cache_url_key(normalized)
        for trace in self.traces.values():
            if trace.cache_key_url == key or trace.normalized_url == normalized:
                return trace
        return None

    def mark_skip(self, url: str, reason: str) -> None:
        trace = self._resolve(url)
        if trace is None:
            if len(self._order) < self.limit:
                self.register_product_url(url)
                trace = self._resolve(url)
            else:
                return
        if trace is None:
            return
        trace.skipped = True
        trace.skip_reason = reason
        self._log_result(trace)

    def before_request(self, url: str, page_type: str) -> None:
        if page_type != "product":
            return
        trace = self._resolve(url)
        if trace is None and len(self._order) < self.limit:
            self.register_product_url(url)
            trace = self._resolve(url)
        if trace and trace.index not in self._logged_pipeline:
            self._log_pipeline(trace)

    def record_response(
        self,
        url: str,
        page_type: str,
        status_code: int,
        final_url: str,
    ) -> None:
        if page_type != "product":
            return
        trace = self._resolve(url)
        if trace is None:
            return
        trace.skipped = False
        trace.skip_reason = None
        trace.http_status = status_code
        trace.redirect_url = final_url if final_url != trace.request_url else None
        trace.exception = None
        self._log_result(trace)

    def record_exception(self, url: str, page_type: str, exc: Exception) -> None:
        if page_type != "product":
            return
        trace = self._resolve(url)
        if trace is None:
            return
        trace.skipped = False
        trace.http_status = getattr(exc, "status_code", None)
        trace.exception = f"{type(exc).__name__}: {exc}"
        self._log_result(trace)

    def finalize(self) -> None:
        if not self._order:
            msg = (
                "[FETCH DIAG] No product URLs registered for fetch diagnostics. "
                "Reason: scan returned 0 items or fetch phase was not started."
            )
            print(msg)
            logger.info(msg)
            return

        never_attempted = 0
        for key in self._order:
            trace = self.traces[key]
            if trace.http_status is None and trace.exception is None and not trace.skip_reason:
                trace.skip_reason = "fetch_never_attempted"
                trace.skipped = True
                never_attempted += 1
                self._log_result(trace)

        if never_attempted:
            msg = (
                f"[FETCH DIAG] {never_attempted} of {len(self._order)} registered URLs "
                "never reached requests.get() — see skip_reason per URL."
            )
            print(msg)
            logger.warning(msg)

        self.write_report()

    def write_report(self) -> None:
        lines = [
            "index\toriginal_href\tnormalized_url\tcache_key\trequest_url\t"
            "skipped\tskip_reason\thttp_status\tredirect_url\texception"
        ]
        for key in self._order:
            t = self.traces[key]
            lines.append(
                f"{t.index}\t{t.original_href}\t{t.normalized_url}\t{t.cache_key_url}\t"
                f"{t.request_url}\t{'yes' if t.skipped else 'no'}\t"
                f"{t.skip_reason or ''}\t{t.http_status or ''}\t"
                f"{t.redirect_url or ''}\t{t.exception or ''}"
            )
        DEBUG_FETCH_PATH.write_text("\n".join(lines), encoding="utf-8")
        print(f"[FETCH DIAG] Report saved: {DEBUG_FETCH_PATH}")
        logger.info("[FETCH DIAG] Report saved: %s", DEBUG_FETCH_PATH)

    def _log_pipeline(self, trace: FetchTrace) -> None:
        if trace.normalized_url in self._logged_pipeline:
            return
        self._logged_pipeline.add(trace.normalized_url)
        block = (
            f"[FETCH DIAG #{trace.index}]\n"
            f"  original href: {trace.original_href}\n"
            f"  after normalize_url(): {trace.normalized_url}\n"
            f"  cache key (after transforms): {trace.cache_key_url}\n"
            f"  requests.get() URL: {trace.request_url}"
        )
        print(block)
        logger.info(block)

    def _log_result(self, trace: FetchTrace) -> None:
        if trace.skip_reason and trace.http_status is None:
            block = (
                f"[FETCH DIAG #{trace.index}] SKIPPED — {trace.skip_reason}\n"
                f"  URL: {trace.request_url}"
            )
        elif trace.exception:
            block = (
                f"[FETCH DIAG #{trace.index}] REQUEST FAILED\n"
                f"  URL: {trace.request_url}\n"
                f"  HTTP status: {trace.http_status or '—'}\n"
                f"  Exception: {trace.exception}"
            )
        else:
            block = (
                f"[FETCH DIAG #{trace.index}] REQUEST OK\n"
                f"  URL: {trace.request_url}\n"
                f"  HTTP status: {trace.http_status}\n"
                f"  Redirect URL: {trace.redirect_url or '—'}"
            )
        print(block)
        logger.info(block)


def begin_fetch_diagnostics(product_urls: list[str], base_url: str, limit: int = 20) -> None:
    collector = FetchDiagnosticsCollector(base_url=base_url, limit=limit)
    for href in product_urls[:limit]:
        collector.register_product_url(href)
    _fetch_diag_ctx.set(collector)


def get_fetch_diagnostics() -> FetchDiagnosticsCollector | None:
    return _fetch_diag_ctx.get()


def end_fetch_diagnostics() -> None:
    collector = _fetch_diag_ctx.get()
    if collector:
        collector.finalize()
    _fetch_diag_ctx.set(None)


def trace_fetch_skip(url: str, reason: str) -> None:
    collector = get_fetch_diagnostics()
    if collector:
        collector.mark_skip(url, reason)
