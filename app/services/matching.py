"""
Сервис автоматического сопоставления товаров по похожести названий.
"""
import re
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.models.enums import MatchStatus, MatchType
from app.models.product import CompetitorProduct, MyProduct, ProductMatch

# Ключевые слова для сравнения названий воздушных шаров
KEYWORDS = [
    "латекс",
    "хром",
    "конфетти",
    "агат",
    "браш",
    "фольга",
    "цифра",
    "сердце",
    "круг",
    "45 см",
    "60 см",
]

# Порог уверенного совпадения (0.0 — 1.0)
CONFIDENT_THRESHOLD = 0.65


def normalize_name(name: str) -> str:
    """
    Нормализация названия:
    - нижний регистр
    - убрать знаки препинания
    - убрать лишние пробелы
    """
    text = name.lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_keywords(normalized_name: str) -> set[str]:
    """Извлечь ключевые слова из нормализованного названия."""
    found = set()
    for keyword in KEYWORDS:
        if keyword in normalized_name:
            found.add(keyword)
    return found


def calculate_similarity(my_name: str, competitor_name: str) -> float:
    """
    Оценить похожесть двух названий.
    Учитывает общие ключевые слова и текстовое сходство.
    """
    norm_my = normalize_name(my_name)
    norm_comp = normalize_name(competitor_name)

    if not norm_my or not norm_comp:
        return 0.0

    # Текстовое сходство (SequenceMatcher)
    text_score = SequenceMatcher(None, norm_my, norm_comp).ratio()

    # Сходство по ключевым словам
    my_keywords = extract_keywords(norm_my)
    comp_keywords = extract_keywords(norm_comp)

    if my_keywords or comp_keywords:
        union = my_keywords | comp_keywords
        if union:
            keyword_score = len(my_keywords & comp_keywords) / len(union)
        else:
            keyword_score = 0.0
    else:
        keyword_score = text_score

    # Итоговая оценка: ключевые слова важнее
    return 0.4 * text_score + 0.6 * keyword_score


def find_best_match(
    competitor_product: CompetitorProduct, my_products: list[MyProduct]
) -> tuple[MyProduct | None, float]:
    """
    Найти наиболее подходящий наш товар для товара конкурента.
    Возвращает (товар, оценка) или (None, 0).
    """
    best_product = None
    best_score = 0.0

    for my_product in my_products:
        score = calculate_similarity(my_product.name, competitor_product.name)
        if score > best_score:
            best_score = score
            best_product = my_product

    return best_product, best_score


def auto_match_products(db: Session) -> int:
    """
    Автоматически сопоставить несопоставленные товары конкурентов.
    Возвращает количество созданных сопоставлений.
    """
    unmatched = (
        db.query(CompetitorProduct)
        .filter(CompetitorProduct.match_status == MatchStatus.UNMATCHED)
        .all()
    )
    my_products = db.query(MyProduct).all()

    if not my_products:
        return 0

    created = 0
    for comp_product in unmatched:
        best, score = find_best_match(comp_product, my_products)

        if best and score >= CONFIDENT_THRESHOLD:
            match = ProductMatch(
                my_product_id=best.id,
                competitor_product_id=comp_product.id,
                match_type=MatchType.AUTO,
                confidence_score=round(score * 100, 2),
            )
            comp_product.match_status = MatchStatus.AUTO_MATCHED
            db.add(match)
            created += 1

    db.commit()
    return created


def get_suggested_match(
    db: Session, competitor_product: CompetitorProduct
) -> tuple[MyProduct | None, float]:
    """
    Получить предполагаемое сопоставление для страницы ручного подтверждения.
    """
    my_products = db.query(MyProduct).all()
    return find_best_match(competitor_product, my_products)


def confirm_match(
    db: Session,
    competitor_product_id: int,
    my_product_id: int,
    match_type: MatchType = MatchType.MANUAL,
    confidence_score: float | None = None,
) -> ProductMatch:
    """Подтвердить сопоставление вручную или автоматически."""
    comp_product = db.get(CompetitorProduct, competitor_product_id)
    if not comp_product:
        raise ValueError("Товар конкурента не найден")

    # Удаляем старое сопоставление, если было
    existing = (
        db.query(ProductMatch)
        .filter(ProductMatch.competitor_product_id == competitor_product_id)
        .first()
    )
    if existing:
        db.delete(existing)

    status = (
        MatchStatus.AUTO_MATCHED
        if match_type == MatchType.AUTO
        else MatchStatus.MANUAL_MATCHED
    )
    comp_product.match_status = status

    match = ProductMatch(
        my_product_id=my_product_id,
        competitor_product_id=competitor_product_id,
        match_type=match_type,
        confidence_score=confidence_score,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def ignore_product(db: Session, competitor_product_id: int) -> None:
    """Пометить товар конкурента как игнорируемый."""
    comp_product = db.get(CompetitorProduct, competitor_product_id)
    if not comp_product:
        raise ValueError("Товар конкурента не найден")

    # Удаляем сопоставление, если было
    existing = (
        db.query(ProductMatch)
        .filter(ProductMatch.competitor_product_id == competitor_product_id)
        .first()
    )
    if existing:
        db.delete(existing)

    comp_product.match_status = MatchStatus.IGNORED
    db.commit()
