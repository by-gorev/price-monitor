"""
Контекст страницы и базовый класс платформенных парсеров.
"""
import time
from collections.abc import Callable

from bs4 import BeautifulSoup

from app.parsers.base import BaseSiteParser
from app.parsers.confidence import compute_strategy_confidence, is_strategy_acceptable
from app.parsers.debug import ScanDebugContext
from app.parsers.html_utils import extract_all_page_links
from app.parsers.http import load_page_html
from app.parsers.page_context import PageContext, StrategyFn
from app.parsers.parser_types import ParsedProduct, ScanResult, ScannedItem, StrategyResult
from app.parsers.product_parse import parse_product_page

__all__ = ["BasePlatformParser", "PageContext", "StrategyFn"]


class BasePlatformParser(BaseSiteParser):
    """
    Парсер CMS со стратегиями сканирования.
    scan_category — только страница категории, без запросов к товарам.
    parse_product — страница товара по необходимости.
    """

    scan_strategies: list[tuple[str, StrategyFn]] = []
    parse_strategies: list[tuple[str, Callable[[str], ParsedProduct | None]]] = []
    default_selectors: dict | None = None

    def scan_category(
        self, url: str, debug: ScanDebugContext | None = None
    ) -> ScanResult:
        ctx = PageContext.load(url, debug=debug, page_type="category")
        return self.scan_category_with_context(ctx, debug=debug)

    def scan_category_with_context(
        self, ctx: PageContext, debug: ScanDebugContext | None = None
    ) -> ScanResult:
        started = time.perf_counter()
        all_links = extract_all_page_links(ctx.soup, ctx.base)

        if debug:
            debug.set_all_links(all_links)

        cms_detected = True
        attempts: list[StrategyResult] = []
        total_rejected = 0
        best: StrategyResult | None = None

        for strategy_name, strategy_fn in self.scan_strategies:
            if debug:
                debug.set_strategy(strategy_name)

            attempt = self._run_strategy(
                strategy_name, strategy_fn, ctx, cms_detected
            )
            attempts.append(attempt)
            total_rejected += attempt.rejected_links

            if best is None or attempt.confidence > best.confidence:
                best = attempt

            if is_strategy_acceptable(attempt):
                break

        elapsed = (time.perf_counter() - started) * 1000

        if best and best.items:
            prices_found = best.prices_found
            without = max(0, len(best.items) - prices_found)
            result = ScanResult(
                items=best.items,
                strategy=best.strategy_name,
                parser_name=self.name,
                platform=self.platform,
                confidence=best.confidence,
                rejected_links=total_rejected,
                raw_candidates=best.raw_candidates,
                prices_found=prices_found,
                without_price=without,
            )
            result.strategy_attempts = attempts
            if debug:
                debug.set_confidence(best.confidence)
                debug.set_scan_stats(
                    found=len(best.items),
                    unique=len(best.items),
                    raw=best.raw_candidates,
                    rejected=total_rejected,
                    urls=[i.url for i in best.items],
                    prices_found=prices_found,
                    without_price=without,
                )
                debug.set_strategy_attempts(attempts)
                debug.set_stage(f"success:{best.strategy_name}")
                debug.set_elapsed(elapsed / 1000)
            return result

        empty = ScanResult(
            items=[],
            parser_name=self.name,
            platform=self.platform,
            confidence=best.confidence if best else 0.0,
            rejected_links=total_rejected,
        )
        empty.strategy_attempts = attempts
        if debug:
            debug.set_strategy_attempts(attempts)
            debug.set_stage(attempts[-1].strategy_name if attempts else "no_strategies")
            debug.set_elapsed(elapsed / 1000)
        return empty

    def _run_strategy(
        self,
        strategy_name: str,
        strategy_fn: StrategyFn,
        ctx: PageContext,
        cms_detected: bool,
    ) -> StrategyResult:
        started = time.perf_counter()
        try:
            raw = strategy_fn(ctx)
            items = raw.items
            names = sum(1 for i in items if i.name and i.name.strip())
            links = sum(1 for i in items if i.url)
            prices = sum(1 for i in items if i.price is not None)

            attempt = StrategyResult(
                strategy_name=strategy_name,
                success=len(items) > 0,
                items=items,
                products_found=len(items),
                links_count=links,
                names_found=names,
                prices_found=prices,
                rejected_links=raw.rejected_links,
                raw_candidates=raw.raw_candidates,
                elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            attempt.confidence = compute_strategy_confidence(attempt, cms_detected)
            attempt.success = is_strategy_acceptable(attempt)
            return attempt
        except Exception as exc:
            attempt = StrategyResult(
                strategy_name=strategy_name,
                success=False,
                error=str(exc),
                elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            attempt.confidence = compute_strategy_confidence(attempt, cms_detected)
            return attempt

    def parse_product(
        self, url: str, selector_config: str | None = None
    ) -> ParsedProduct:
        from app.parsers.http import get_listing_price

        listing = get_listing_price(url)
        if listing is not None:
            name, price = listing
            return ParsedProduct(name=name, price=price)

        html = load_page_html(url, page_type="product")
        selectors = self._load_selectors(selector_config)
        return parse_product_page(
            html=html,
            url=url,
            selectors=selectors,
            strategies=self.parse_strategies,
        )

    def default_selector_config(self) -> str | None:
        if not self.default_selectors:
            return None
        from app.parsers.utils import selector_config_json

        return selector_config_json(self.default_selectors)

    def _load_selectors(self, selector_config: str | None) -> dict | None:
        if not self.default_selectors and not selector_config:
            return None
        selectors = (self.default_selectors or {}).copy()
        if selector_config:
            import json

            try:
                selectors.update(json.loads(selector_config))
            except json.JSONDecodeError:
                pass
        return selectors

    @staticmethod
    def html_contains(html: str, *markers: str) -> bool:
        if not html:
            return False
        lower = html.lower()
        return any(marker.lower() in lower for marker in markers)

    @staticmethod
    def meta_contains(soup: BeautifulSoup, *markers: str) -> bool:
        for tag in soup.find_all("meta"):
            content = " ".join(
                str(tag.get(attr, ""))
                for attr in ("content", "name", "property", "generator")
            ).lower()
            if any(marker.lower() in content for marker in markers):
                return True
        return False
