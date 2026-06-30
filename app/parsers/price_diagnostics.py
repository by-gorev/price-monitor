"""
Диагностика извлечения цены на странице товара.
"""
from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path

from app.parsers.price_extract import PriceCandidate

logger = logging.getLogger(__name__)

DEBUG_PRICE_PATH = (
    Path(__file__).resolve().parent.parent.parent / "debug_last_prices.txt"
)

_price_diag_ctx: ContextVar[PriceDiagnosticsCollector | None] = ContextVar(
    "price_diag_ctx", default=None
)


@dataclass
class ProductPriceTrace:
    index: int
    url: str
    name: str
    candidates: list[PriceCandidate] = field(default_factory=list)
    selected: float | None = None


class PriceDiagnosticsCollector:
    def __init__(self, limit: int = 20):
        self.limit = limit
        self.traces: list[ProductPriceTrace] = []

    def record(
        self,
        url: str,
        name: str,
        candidates: list[PriceCandidate],
        selected: float | None,
    ) -> None:
        if len(self.traces) >= self.limit:
            return
        trace = ProductPriceTrace(
            index=len(self.traces) + 1,
            url=url,
            name=name,
            candidates=list(candidates),
            selected=selected,
        )
        self.traces.append(trace)
        self._log_trace(trace)

    def finalize(self) -> None:
        if not self.traces:
            msg = "[PRICE DIAG] No product price traces recorded."
            print(msg)
            logger.info(msg)
            return
        self.write_report()
        print(f"[PRICE DIAG] Report saved: {DEBUG_PRICE_PATH}")
        logger.info("[PRICE DIAG] Report saved: %s", DEBUG_PRICE_PATH)

    def write_report(self) -> None:
        lines: list[str] = []
        for trace in self.traces:
            lines.append(f"#{trace.index}\tURL\t{trace.url}")
            lines.append(f"#{trace.index}\tName\t{trace.name}")
            for candidate in trace.candidates:
                lines.append(
                    f"#{trace.index}\tcandidate\t{candidate.selector}\t"
                    f"{candidate.raw}\t{candidate.normalized or ''}"
                )
            lines.append(
                f"#{trace.index}\tselected\t{trace.selected if trace.selected is not None else ''}"
            )
            lines.append("")
        DEBUG_PRICE_PATH.write_text("\n".join(lines), encoding="utf-8")

    def _log_trace(self, trace: ProductPriceTrace) -> None:
        block_lines = [
            f"[PRICE DIAG #{trace.index}]",
            f"  URL: {trace.url}",
            f"  Name: {trace.name}",
            "  Price candidates:",
        ]
        if not trace.candidates:
            block_lines.append("    (none)")
        else:
            for candidate in trace.candidates:
                block_lines.extend(
                    [
                        f"    selector: {candidate.selector}",
                        f"    raw: {candidate.raw}",
                        f"    normalized: {candidate.normalized if candidate.normalized is not None else '—'}",
                        "    ----------------",
                    ]
                )
        block_lines.append(
            f"  Selected price: {trace.selected if trace.selected is not None else '—'}"
        )
        block = "\n".join(block_lines)
        print(block)
        logger.info(block)

    def to_dict(self) -> list[dict]:
        return [
            {
                "url": trace.url,
                "name": trace.name,
                "price_candidates": [
                    {
                        "selector": c.selector,
                        "raw": c.raw,
                        "normalized": c.normalized,
                    }
                    for c in trace.candidates
                ],
                "selected_price": trace.selected,
            }
            for trace in self.traces
        ]


def begin_price_diagnostics(limit: int = 20) -> None:
    _price_diag_ctx.set(PriceDiagnosticsCollector(limit=limit))


def get_price_diagnostics() -> PriceDiagnosticsCollector | None:
    return _price_diag_ctx.get()


def end_price_diagnostics() -> list[dict]:
    collector = _price_diag_ctx.get()
    traces: list[dict] = []
    if collector:
        collector.finalize()
        traces = collector.to_dict()
    _price_diag_ctx.set(None)
    return traces


def trace_product_price(
    url: str,
    name: str,
    candidates: list[PriceCandidate],
    selected: float | None,
) -> None:
    collector = get_price_diagnostics()
    if collector:
        collector.record(url, name, candidates, selected)
