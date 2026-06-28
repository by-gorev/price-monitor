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
        if category:
            existing.category_id = category.id
            existing.match_status = MatchStatus.AUTO_MATCHED
        return existing, False

    product = CompetitorProduct(
        competitor_id=competitor_id,
        name=item.name,
        url=item.url,
        category_id=category.id if category else None,
        match_status=(
            MatchStatus.AUTO_MATCHED if category else MatchStatus.UNMATCHED
        ),
        selector_config=selector_config,
    )
    db.add(product)
    db.flush()
    return product, True


def _update_prices(db: Session, products: list[CompetitorProduct]) -> int:
    """Обновить цены через parser_service для поддерживаемого конкурента."""
    updated = 0
    for product in products:
        if not product.url or not product.competitor:
            continue
        if not is_supported_competitor(product.competitor):
            continue
        if parse_and_save(db, product):
            updated += 1
    return updated


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

    parser = get_parser_for_url(comp_category.category_url, debug=debug)
    selector_config = parser.default_selector_config() if parser else None

    if parser:
        result = parser.scan_category(comp_category.category_url, debug=debug)
        items = result.items
        debug.finish(len(items))
        scan_debug = debug.to_dict()
        scan_debug["strategy"] = result.strategy
        scan_debug["rejected_links"] = result.rejected_links
    else:
        items = []
        debug.finish(0)
        scan_debug = debug.to_dict()
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
    prices_updated = _update_prices(db, touched_with_competitor)

    return {
        "found": len(items),
        "created": created,
        "updated": updated,
        "prices_updated": prices_updated,
        "category_name": comp_category.product_category.name,
        "competitor_name": comp_category.competitor.name,
        "scan_debug": scan_debug,
    }
