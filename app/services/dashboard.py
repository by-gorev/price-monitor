"""
Сервис для расчёта статистики на главной странице (dashboard)
и агрегированного сравнения цен по рыночным категориям.
"""
from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.enums import MatchStatus
from app.models.product import CompetitorProduct, PriceSnapshot, ProductCategory

MATCHED_STATUSES = (MatchStatus.AUTO_MATCHED, MatchStatus.MANUAL_MATCHED)


def _latest_snapshot(db: Session, product_id: int) -> PriceSnapshot | None:
    """Последний снимок цены для товара."""
    return (
        db.query(PriceSnapshot)
        .filter(PriceSnapshot.competitor_product_id == product_id)
        .order_by(PriceSnapshot.checked_at.desc())
        .first()
    )


def get_category_comparisons(db: Session) -> list[dict]:
    """
    Сравнение по рыночным категориям: одна строка на категорию
    с агрегированными ценами конкурентов.
    """
    products = (
        db.query(CompetitorProduct)
        .options(
            joinedload(CompetitorProduct.competitor),
            joinedload(CompetitorProduct.category),
        )
        .filter(
            CompetitorProduct.match_status.in_(MATCHED_STATUSES),
            CompetitorProduct.category_id.isnot(None),
        )
        .all()
    )

    grouped: dict[int, dict] = {}

    for product in products:
        category = product.category
        if not category:
            continue

        snapshot = _latest_snapshot(db, product.id)
        if not snapshot:
            continue

        price = float(snapshot.price)
        checked_at = snapshot.checked_at

        if category.id not in grouped:
            grouped[category.id] = {
                "category_id": category.id,
                "category_name": category.name,
                "my_price": float(category.my_price),
                "prices": [],
                "last_checked_at": None,
            }

        entry = grouped[category.id]
        entry["prices"].append(price)
        if entry["last_checked_at"] is None or checked_at > entry["last_checked_at"]:
            entry["last_checked_at"] = checked_at

    comparisons = []
    for entry in grouped.values():
        prices = entry.pop("prices")
        entry["product_count"] = len(prices)
        entry["min_price"] = min(prices)
        entry["max_price"] = max(prices)
        entry["avg_price"] = round(sum(prices) / len(prices), 2)
        entry["diff_vs_avg"] = round(entry["my_price"] - entry["avg_price"], 2)
        comparisons.append(entry)

    return sorted(comparisons, key=lambda x: abs(x["diff_vs_avg"]), reverse=True)


def get_category_comparison_detail(db: Session, category_id: int) -> dict | None:
    """Детали категории: сводка и список товаров конкурентов с ценами."""
    category = db.get(ProductCategory, category_id)
    if not category:
        return None

    products = (
        db.query(CompetitorProduct)
        .options(joinedload(CompetitorProduct.competitor))
        .filter(
            CompetitorProduct.category_id == category_id,
            CompetitorProduct.match_status.in_(MATCHED_STATUSES),
        )
        .order_by(CompetitorProduct.name)
        .all()
    )

    product_rows = []
    prices: list[float] = []
    last_checked_at: datetime | None = None

    for product in products:
        snapshot = _latest_snapshot(db, product.id)
        price = float(snapshot.price) if snapshot else None
        checked_at = snapshot.checked_at if snapshot else None

        if price is not None:
            prices.append(price)
        if checked_at and (last_checked_at is None or checked_at > last_checked_at):
            last_checked_at = checked_at

        product_rows.append(
            {
                "id": product.id,
                "name": product.name,
                "competitor_name": product.competitor.name,
                "url": product.url,
                "price": price,
                "checked_at": checked_at,
            }
        )

    summary = {
        "category_id": category.id,
        "category_name": category.name,
        "my_price": float(category.my_price),
        "product_count": len(prices),
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
        "last_checked_at": last_checked_at,
        "diff_vs_avg": (
            round(float(category.my_price) - sum(prices) / len(prices), 2)
            if prices
            else None
        ),
    }

    return {
        "category": category,
        "summary": summary,
        "products": product_rows,
    }


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

    comparisons = get_category_comparisons(db)
    my_higher = sum(1 for c in comparisons if c["diff_vs_avg"] > 0)
    my_lower = sum(1 for c in comparisons if c["diff_vs_avg"] < 0)

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
