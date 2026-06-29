"""
Расчёт confidence для стратегий и парсеров.
"""
from app.parsers.parser_types import ParserRunResult, StrategyResult

MIN_PARSER_CONFIDENCE = 0.5
MIN_STRATEGY_PRODUCTS = 3


def compute_strategy_confidence(
    result: StrategyResult,
    cms_detected: bool,
) -> float:
    """Confidence стратегии (0.0 – 1.0)."""
    if not result.items:
        return 0.1 if cms_detected else 0.05

    n = len(result.items)
    name_ratio = result.names_found / n
    link_ratio = result.links_count / n
    price_ratio = result.prices_found / min(n, 3)

    score = 0.0
    if cms_detected:
        score += 0.25
    score += min(n / 20.0, 0.25)
    score += name_ratio * 0.15
    score += link_ratio * 0.15
    score += price_ratio * 0.20

    if result.products_found >= MIN_STRATEGY_PRODUCTS:
        score += 0.05
    if result.error:
        score *= 0.5

    return round(min(score, 0.99), 2)


def compute_parser_confidence(run: ParserRunResult) -> float:
    """Итоговый confidence Parser на основе лучшей стратегии."""
    if not run.strategy_attempts:
        return 0.05

    best = max(run.strategy_attempts, key=lambda s: s.confidence)
    score = best.confidence

    if run.cms_detected:
        score = min(score + 0.05, 0.99)
    if run.products_found < MIN_STRATEGY_PRODUCTS:
        score *= 0.6
    if run.prices_found == 0:
        score *= 0.5

    if run.parser_name == "unknown":
        score = min(score, 0.65)

    return round(min(score, 0.99), 2)


def is_strategy_acceptable(result: StrategyResult) -> bool:
    return result.acceptable and result.confidence >= 0.4


def is_parser_acceptable(run: ParserRunResult) -> bool:
    return (
        run.products_found >= MIN_STRATEGY_PRODUCTS
        and run.confidence >= MIN_PARSER_CONFIDENCE
    )
