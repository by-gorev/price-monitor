"""
Сервис для расчёта статистики на главной странице (dashboard).
"""
from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.enums import MatchStatus
from app.models.product import CompetitorProduct, PriceSnapshot


def get_dashboard_stats(db: Session) -> dict:
    """Собрать все показатели для dashboard."""
    today_start = datetime.combine(date.today(), datetime.min.time())

    prices_checked_today = (
        db.query(func.count(PriceSnapshot.id))
        .filter(PriceSnapshot.checked_at >= today_start)
        .scalar()
        or 0
    )

    price_changes = _get_price_changes(db)
    increased = sum(1 for c in price_changes if c["change_rub"] > 0)
    decreased = sum(1 for c in price_changes if c["change_rub"] < 0)

    comparisons = _get_price_comparisons(db)
    my_higher = sum(1 for c in comparisons if c["diff"] > 0)
    my_lower = sum(1 for c in comparisons if c["diff"] < 0)

    unmatched_count = (
        db.query(func.count(CompetitorProduct.id))
        .filter(CompetitorProduct.match_status == MatchStatus.UNMATCHED)
        .scalar()
        or 0
    )

    return {
        "prices_checked_today": prices_checked_today,
        "increased": increased,
        "decreased": decreased,
        "my_higher": my_higher,
        "my_lower": my_lower,
        "unmatched_count": unmatched_count,
        "comparisons": comparisons[:10],
        "price_changes": price_changes[:10],
    }


def _get_price_changes(db: Session) -> list[dict]:
    """Найти товары с изменившейся ценой (два последних снимка)."""
    changes = []
    products = (
        db.query(CompetitorProduct)
        .options(joinedload(CompetitorProduct.competitor))
        .all()
    )

    for product in products:
        snapshots = (
            db.query(PriceSnapshot)
            .filter(PriceSnapshot.competitor_product_id == product.id)
            .order_by(PriceSnapshot.checked_at.desc())
            .limit(2)
            .all()
        )
        if len(snapshots) < 2:
            continue

        new_price = float(snapshots[0].price)
        old_price = float(snapshots[1].price)
        change_rub = new_price - old_price
        if change_rub == 0:
            continue

        change_pct = (change_rub / old_price * 100) if old_price else 0
        changes.append(
            {
                "product_name": product.name,
                "competitor_name": product.competitor.name,
                "old_price": old_price,
                "new_price": new_price,
                "change_rub": change_rub,
                "change_pct": round(change_pct, 1),
            }
        )

    return sorted(changes, key=lambda x: abs(x["change_rub"]), reverse=True)


def _get_price_comparisons(db: Session) -> list[dict]:
    """
    Сравнить нашу цену по категории с ценами конкурентов
    в той же категории.
    """
    comparisons = []
    products = (
        db.query(CompetitorProduct)
        .options(
            joinedload(CompetitorProduct.competitor),
            joinedload(CompetitorProduct.category),
        )
        .filter(
            CompetitorProduct.match_status.in_(
                [MatchStatus.AUTO_MATCHED, MatchStatus.MANUAL_MATCHED]
            ),
            CompetitorProduct.category_id.isnot(None),
        )
        .all()
    )

    for comp_product in products:
        category = comp_product.category
        if not category:
            continue

        last_snapshot = (
            db.query(PriceSnapshot)
            .filter(PriceSnapshot.competitor_product_id == comp_product.id)
            .order_by(PriceSnapshot.checked_at.desc())
            .first()
        )
        if not last_snapshot:
            continue

        my_price = float(category.my_price)
        comp_price = float(last_snapshot.price)
        diff = my_price - comp_price

        comparisons.append(
            {
                "category_name": category.name,
                "competitor_name": comp_product.competitor.name,
                "competitor_product_name": comp_product.name,
                "my_price": my_price,
                "competitor_price": comp_price,
                "diff": diff,
            }
        )

    return sorted(comparisons, key=lambda x: abs(x["diff"]), reverse=True)


def get_price_history(db: Session) -> list[dict]:
    """История изменений цен для страницы «История цен»."""
    history = []
    products = (
        db.query(CompetitorProduct)
        .options(
            joinedload(CompetitorProduct.competitor),
            joinedload(CompetitorProduct.category),
        )
        .all()
    )

    for product in products:
        snapshots = (
            db.query(PriceSnapshot)
            .filter(PriceSnapshot.competitor_product_id == product.id)
            .order_by(PriceSnapshot.checked_at.desc())
            .limit(2)
            .all()
        )
        if len(snapshots) < 2:
            continue

        new_snap = snapshots[0]
        old_snap = snapshots[1]
        new_price = float(new_snap.price)
        old_price = float(old_snap.price)
        change_rub = new_price - old_price
        change_pct = (change_rub / old_price * 100) if old_price else 0

        category_name = product.category.name if product.category else "—"

        history.append(
            {
                "category_name": category_name,
                "competitor_name": product.competitor.name,
                "competitor_product_name": product.name,
                "old_price": old_price,
                "new_price": new_price,
                "change_rub": change_rub,
                "change_pct": round(change_pct, 1),
                "checked_at": new_snap.checked_at,
            }
        )

    return sorted(history, key=lambda x: x["checked_at"], reverse=True)
