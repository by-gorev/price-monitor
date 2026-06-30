"""
Сканирование страниц категорий конкурентов.
"""
import logging

from sqlalchemy.orm import Session, joinedload

from app.config import SCANNER_DEBUG
from app.models.competitor import CompetitorCategory
from app.models.enums import MatchStatus
from app.models.product import CompetitorProduct, ProductCategory
from app.parsers.debug import ScanDebugContext
from app.parsers.registry import get_parser_for_url
from app.parsers.scan_diagnostics import format_scan_error
from app.parsers.fetch_diagnostics import (
    begin_fetch_diagnostics,
    end_fetch_diagnostics,
    trace_fetch_skip,
)
from app.parsers.http import base_url_from
from app.parsers.price_diagnostics import begin_price_diagnostics, end_price_diagnostics
from app.parsers.debug_store import apply_final_scan_stats, set_last_price_debug
from app.services.matching import find_category_by_keywords
from app.services.parser_service import is_supported_competitor, parse_and_save

logger = logging.getLogger(__name__)


def _upsert_competitor_product(
    db: Session,
    competitor_id: int,
    item,
    categories: list[ProductCategory],
    selector_config: str | None,
) -> tuple[CompetitorProduct, bool]:
    """
    Создать или обновить товар конкурента.
    Возвращает (товар, created).
    """
    category = find_category_by_keywords(item.name, categories)
    auto_cat_id = category.id if category else None
    existing = (
        db.query(CompetitorProduct)
        .filter(
            CompetitorProduct.competitor_id == competitor_id,
            CompetitorProduct.url == item.url,
        )
        .first()
    )

    if existing:
        existing.name = item.name
        existing.url = item.url
        existing.auto_category_id = auto_cat_id
        if not existing.manual_override:
            existing.category_id = auto_cat_id
            existing.match_status = (
                MatchStatus.AUTO_MATCHED if auto_cat_id else MatchStatus.UNMATCHED
            )
        return existing, False

    product = CompetitorProduct(
        competitor_id=competitor_id,
        name=item.name,
        url=item.url,
        category_id=auto_cat_id,
        auto_category_id=auto_cat_id,
        match_status=(
            MatchStatus.AUTO_MATCHED if auto_cat_id else MatchStatus.UNMATCHED
        ),
        manual_override=False,
        selector_config=selector_config,
    )
    db.add(product)
    db.flush()
    return product, True


def _update_prices(db: Session, products: list[CompetitorProduct]) -> dict:
    """Обновить цены через parser_service для поддерживаемого конкурента."""
    stats = {
        "saved": 0,
        "with_price": 0,
        "without_price": 0,
        "parse_errors": 0,
        "skipped": 0,
    }
    for product in products:
        if product.match_status == MatchStatus.IGNORED:
            trace_fetch_skip(product.url or "", "ignored_product")
            stats["skipped"] += 1
            continue
        if not product.url or not product.competitor:
            trace_fetch_skip(product.url or "", "no_url_or_competitor")
            stats["skipped"] += 1
            continue
        if not is_supported_competitor(product.competitor):
            trace_fetch_skip(product.url, "unsupported_competitor")
            stats["skipped"] += 1
            continue
        if parse_and_save(db, product):
            stats["saved"] += 1
            stats["with_price"] += 1
        else:
            stats["parse_errors"] += 1
            stats["without_price"] += 1
            from app.parsers.fetch_diagnostics import get_fetch_diagnostics

            diag = get_fetch_diagnostics()
            trace = diag._resolve(product.url) if diag else None
            if trace and trace.http_status is None and not trace.skip_reason:
                trace_fetch_skip(product.url, "parse_and_save_failed")
    return stats


def scan_category(db: Session, competitor_category_id: int) -> dict:
    """
    Сканировать страницу категории конкурента:
    - найти товары (название + URL);
    - создать или обновить CompetitorProduct;
    - назначить рыночную категорию по keywords;
    - обновить цены через parser_service.
    """
    comp_category = (
        db.query(CompetitorCategory)
        .options(
            joinedload(CompetitorCategory.competitor),
            joinedload(CompetitorCategory.product_category),
        )
        .filter(CompetitorCategory.id == competitor_category_id)
        .first()
    )
    if not comp_category:
        raise ValueError("Запись категории конкурента не найдена")

    debug = ScanDebugContext(enabled=SCANNER_DEBUG)
    debug.url = comp_category.category_url

    items: list = []
    scan_extra: dict = {}
    scan_error: str | None = None
    selector_config = None
    parser = None

    try:
        parser = get_parser_for_url(comp_category.category_url, debug=debug)
        selector_config = parser.default_selector_config() if parser else None

        if parser:
            result = parser.scan_category(comp_category.category_url, debug=debug)
            items = result.items
            scan_error = getattr(result, "error", None)
            debug.finish(len(items), scan_error=scan_error)
            scan_extra = {
                "strategy": result.strategy,
                "rejected_links": result.rejected_links,
                "diagnostics": getattr(result, "diagnostics_summary", {}),
            }
        else:
            debug.finish(0)
    except Exception as exc:
        scan_error = format_scan_error(exc)
        logger.error(
            "Category scan failed for %s: %s",
            comp_category.category_url,
            scan_error,
            exc_info=True,
        )
        debug.set_scan_error(scan_error)
        debug.finish(0, scan_error=scan_error)
        items = []

    categories = db.query(ProductCategory).all()

    created = 0
    updated = 0
    touched: list[CompetitorProduct] = []

    for item in items:
        product, is_new = _upsert_competitor_product(
            db,
            comp_category.competitor_id,
            item,
            categories,
            selector_config,
        )
        touched.append(product)
        if is_new:
            created += 1
        else:
            updated += 1

    db.commit()

    for product in touched:
        db.refresh(product)

    touched_with_competitor = (
        db.query(CompetitorProduct)
        .options(joinedload(CompetitorProduct.competitor))
        .filter(CompetitorProduct.id.in_([p.id for p in touched]))
        .all()
    )
    if items and SCANNER_DEBUG:
        begin_fetch_diagnostics(
            [item.url for item in items if item.url],
            base_url_from(comp_category.category_url),
        )
        begin_price_diagnostics()
    price_stats = _update_prices(db, touched_with_competitor)
    price_debug: list[dict] = []
    if items and SCANNER_DEBUG:
        end_fetch_diagnostics()
        price_debug = end_price_diagnostics()
        set_last_price_debug(price_debug)

    debug.finalize_prices(len(items), price_stats)
    apply_final_scan_stats(
        found=len(items),
        saved=price_stats["saved"],
        with_price=price_stats["with_price"],
        without_price=price_stats["without_price"],
        parse_errors=price_stats["parse_errors"],
        skipped=price_stats["skipped"],
        created=created,
        updated=updated,
    )
    scan_debug = debug.to_dict()
    scan_debug.update(scan_extra)

    return {
        "found": len(items),
        "created": created,
        "updated": updated,
        "prices_updated": price_stats["saved"],
        "price_stats": price_stats,
        "category_name": comp_category.product_category.name,
        "competitor_name": comp_category.competitor.name,
        "scan_debug": scan_debug,
        "scan_error": scan_error,
        "price_debug": price_debug,
    }
