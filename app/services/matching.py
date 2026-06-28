"""
Сервис автоматического назначения рыночных категорий товарам конкурентов.
Ключевые слова берутся из поля ProductCategory.keywords.
"""
from sqlalchemy.orm import Session

from app.models.enums import MatchStatus, MatchType
from app.models.product import CompetitorProduct, ProductCategory


def parse_keywords(keywords_text: str | None) -> list[str]:
    """Разобрать строку ключевых слов (через запятую)."""
    if not keywords_text:
        return []
    return [kw.strip() for kw in keywords_text.split(",") if kw.strip()]


def find_category_by_keywords(
    product_name: str, categories: list[ProductCategory]
) -> ProductCategory | None:
    """
    Найти категорию по первому совпавшему ключевому слову.
    Поиск без учёта регистра. Порядок: категории по id, слова слева направо.
    """
    name_lower = product_name.lower()

    for category in sorted(categories, key=lambda c: c.id):
        for keyword in parse_keywords(category.keywords):
            if keyword.lower() in name_lower:
                return category

    return None


def find_best_category(
    competitor_product: CompetitorProduct, categories: list[ProductCategory]
) -> tuple[ProductCategory | None, float]:
    """Найти категорию для товара. Оценка 100 при совпадении, иначе 0."""
    matched = find_category_by_keywords(competitor_product.name, categories)
    return matched, 100.0 if matched else 0.0


def auto_match_products(db: Session) -> int:
    """
    Автоматически назначить категории несопоставленным товарам конкурентов.
    Без совпадения ключевых слов товар остаётся без категории.
    """
    unmatched = (
        db.query(CompetitorProduct)
        .filter(CompetitorProduct.match_status == MatchStatus.UNMATCHED)
        .all()
    )
    categories = db.query(ProductCategory).all()
    if not categories:
        return 0

    assigned = 0
    for comp_product in unmatched:
        category = find_category_by_keywords(comp_product.name, categories)
        if category:
            comp_product.category_id = category.id
            comp_product.match_status = MatchStatus.AUTO_MATCHED
            assigned += 1

    db.commit()
    return assigned


def get_suggested_category(
    db: Session, competitor_product: CompetitorProduct
) -> tuple[ProductCategory | None, float]:
    """Предполагаемая категория для страницы ручного подтверждения."""
    categories = db.query(ProductCategory).all()
    return find_best_category(competitor_product, categories)


def confirm_category(
    db: Session,
    competitor_product_id: int,
    category_id: int,
    match_type: MatchType = MatchType.MANUAL,
) -> CompetitorProduct:
    """Назначить категорию товару конкурента вручную или автоматически."""
    comp_product = db.get(CompetitorProduct, competitor_product_id)
    if not comp_product:
        raise ValueError("Товар конкурента не найден")

    category = db.get(ProductCategory, category_id)
    if not category:
        raise ValueError("Категория не найдена")

    comp_product.category_id = category_id
    comp_product.match_status = (
        MatchStatus.AUTO_MATCHED
        if match_type == MatchType.AUTO
        else MatchStatus.MANUAL_MATCHED
    )
    db.commit()
    db.refresh(comp_product)
    return comp_product


def ignore_product(db: Session, competitor_product_id: int) -> None:
    """Пометить товар конкурента как игнорируемый."""
    comp_product = db.get(CompetitorProduct, competitor_product_id)
    if not comp_product:
        raise ValueError("Товар конкурента не найден")

    comp_product.category_id = None
    comp_product.match_status = MatchStatus.IGNORED
    db.commit()
