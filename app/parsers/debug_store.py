"""
Хранилище записей диагностики парсеров.
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class StrategyAttemptRecord:
    strategy_name: str
    confidence: float
    products_found: int
    prices_found: int
    links_count: int
    elapsed_ms: float
    error: str | None = None
    accepted: bool = False


@dataclass
class ParserAttemptRecord:
    parser_name: str
    platform: str
    confidence: float
    products_found: int
    strategy_name: str | None
    cms_detected: bool
    elapsed_ms: float
    strategies: list[StrategyAttemptRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class ScanRunRecord:
    url: str
    timestamp: datetime
    platform: str
    parser_name: str
    strategy_name: str | None
    confidence: float
    products_found: int
    unique_count: int
    prices_found: int
    without_price: int
    elapsed_ms: float
    errors: list[str] = field(default_factory=list)
    parser_attempts: list[ParserAttemptRecord] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


_HISTORY: list[ScanRunRecord] = []
_LAST_SUMMARY: dict = {}


def record_scan_run(record: ScanRunRecord) -> None:
    _HISTORY.insert(0, record)
    if len(_HISTORY) > 50:
        _HISTORY.pop()


def set_last_scan_summary(summary: dict) -> None:
    global _LAST_SUMMARY
    _LAST_SUMMARY = summary


def get_last_scan_summary() -> dict:
    return dict(_LAST_SUMMARY)


def get_scan_history(limit: int = 20) -> list[ScanRunRecord]:
    return _HISTORY[:limit]
