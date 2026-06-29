"""
Оркестратор: один Parser на домен, без перебора CMS.
"""
import time

from app.parsers.base import BaseSiteParser, ParserRunResult, ScanResult
from app.parsers.confidence import compute_parser_confidence
from app.parsers.debug import ScanDebugContext
from app.parsers.debug_store import (
    ParserAttemptRecord,
    ScanRunRecord,
    StrategyAttemptRecord,
    record_scan_run,
    set_last_scan_summary,
)
from app.parsers.domain_cache import get_cached_parser_name
from app.parsers.http import begin_http_scan, log_http_stats
from app.parsers.page_context import PageContext


class OrchestratedParser(BaseSiteParser):
    """
    Обёртка для scanner_service: использует Parser домена,
    без перебора остальных CMS если домен уже известен.
    """

    name = "orchestrator"
    platform = "Auto"

    def __init__(
        self,
        parsers: list[BaseSiteParser],
        fallback: BaseSiteParser,
        primary: BaseSiteParser,
        domain: str,
        domain_cached: bool = False,
        platform: str = "Auto",
    ):
        self._parsers = parsers
        self._fallback = fallback
        self._primary = primary
        self._winner: BaseSiteParser | None = primary
        self._domain = domain
        self._domain_cached = domain_cached
        self.platform = platform

    def detect(self, url: str, html: str | None = None) -> bool:
        return True

    def scan_category(
        self, url: str, debug: ScanDebugContext | None = None
    ) -> ScanResult:
        begin_http_scan()
        started = time.perf_counter()

        ctx = PageContext.load(url, debug=debug, page_type="category")
        parser = self._primary
        self._winner = parser

        if debug:
            debug.set_platform(parser.platform)
            debug.set_adapter(parser.name)

        run = self._evaluate_parser(parser, url, ctx, debug)
        runs = [run]
        elapsed_sec = time.perf_counter() - started

        if debug:
            debug.set_confidence(run.confidence)
            debug.record_parser_attempts(runs)

        log_http_stats(platform=parser.platform, elapsed_sec=elapsed_sec)

        elapsed_ms = round(elapsed_sec * 1000, 1)
        record = self._build_run_record(url, run, runs, elapsed_ms)
        record_scan_run(record)
        set_last_scan_summary(record.summary)

        if not run.items:
            result = ScanResult(
                items=[],
                parser_name=run.parser_name,
                platform=run.platform,
                confidence=run.confidence,
                parser_attempts=runs,
            )
            if debug:
                debug.finish(0)
            return result

        from app.parsers.http import cache_listing_prices

        cache_listing_prices(run.items)

        result = ScanResult(
            items=run.items,
            strategy=run.strategy_name,
            parser_name=run.parser_name,
            platform=run.platform,
            confidence=run.confidence,
            rejected_links=run.rejected_links,
            prices_found=run.prices_found,
            without_price=run.without_price,
            parser_attempts=runs,
        )
        if debug:
            debug.finish(len(run.items))
        return result

    def parse_product(self, url: str, selector_config: str | None = None):
        parser = self._winner or self._primary
        return parser.parse_product(url, selector_config)

    def default_selector_config(self) -> str | None:
        parser = self._winner or self._primary
        return parser.default_selector_config()

    def _evaluate_parser(
        self,
        parser: BaseSiteParser,
        url: str,
        ctx: PageContext,
        debug: ScanDebugContext | None,
    ) -> ParserRunResult:
        cms_detected = parser.name == get_cached_parser_name(self._domain)

        if hasattr(parser, "scan_category_with_context"):
            scan = parser.scan_category_with_context(ctx, debug=debug)  # type: ignore
        else:
            scan = parser.scan_category(url, debug=debug)

        attempts = getattr(scan, "strategy_attempts", [])
        run = ParserRunResult(
            parser_name=parser.name,
            platform=parser.platform,
            products_found=len(scan.items),
            strategy_name=scan.strategy,
            items=scan.items,
            strategy_attempts=attempts,
            prices_found=getattr(scan, "prices_found", 0),
            without_price=getattr(scan, "without_price", 0),
            unique_count=len(scan.items),
            rejected_links=scan.rejected_links,
            cms_detected=cms_detected,
            errors=[],
        )
        run.confidence = compute_parser_confidence(run)
        run.success = run.products_found >= 3 and run.confidence >= 0.5
        return run

    def _build_run_record(
        self,
        url: str,
        best: ParserRunResult,
        runs: list[ParserRunResult],
        elapsed_ms: float,
    ) -> ScanRunRecord:
        parser_attempts = []
        for run in runs:
            strategies = [
                StrategyAttemptRecord(
                    strategy_name=s.strategy_name,
                    confidence=s.confidence,
                    products_found=s.products_found,
                    prices_found=s.prices_found,
                    links_count=s.links_count,
                    elapsed_ms=s.elapsed_ms,
                    error=s.error,
                    accepted=s.success,
                )
                for s in run.strategy_attempts
            ]
            parser_attempts.append(
                ParserAttemptRecord(
                    parser_name=run.parser_name,
                    platform=run.platform,
                    confidence=run.confidence,
                    products_found=run.products_found,
                    strategy_name=run.strategy_name,
                    cms_detected=run.cms_detected,
                    elapsed_ms=run.elapsed_ms,
                    strategies=strategies,
                    errors=run.errors,
                )
            )

        summary = {
            "cms": best.platform,
            "parser": best.parser_name,
            "strategy": best.strategy_name,
            "found": best.products_found,
            "unique": best.unique_count,
            "with_price": best.prices_found,
            "without_price": best.without_price,
            "confidence": best.confidence,
            "errors": sum(len(r.errors) for r in runs),
            "duplicates": 0,
            "skipped": 0,
            "created": 0,
            "updated": 0,
        }

        return ScanRunRecord(
            url=url,
            timestamp=__import__("datetime").datetime.utcnow(),
            platform=best.platform,
            parser_name=best.parser_name,
            strategy_name=best.strategy_name,
            confidence=best.confidence,
            products_found=best.products_found,
            unique_count=best.unique_count,
            prices_found=best.prices_found,
            without_price=best.without_price,
            elapsed_ms=elapsed_ms,
            errors=[e for r in runs for e in r.errors],
            parser_attempts=parser_attempts,
            summary=summary,
        )
