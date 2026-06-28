"""
Аналитика рынка на основе сопоставленных товаров и последних снимков цен.
"""
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models.competitor import Competitor
from app.models.enums import MatchStatus
from app.models.product import CompetitorProduct, PriceSnapshot

MATCHED_STATUSES = (MatchStatus.AUTO_MATCHED, MatchStatus.MANUAL_MATCHED)


def price_indicator_class(deviation_pct: float | None) -> str:
    """
    Цветовая индикация отклонения моей цены от средней:
    ниже средней — зелёный, ±3% — жёлтый, выше — красный.
    """
    if deviation_pct is None:
        return ""
    if deviation_pct < -3:
        return "price-good"
    if deviation_pct > 3:
        return "price-bad"
    return "price-neutral"


def _latest_snapshot(db: Session, product_id: int) -> PriceSnapshot | None:
    return (
        db.query(PriceSnapshot)
        .filter(PriceSnapshot.competitor_product_id == product_id)
        .order_by(PriceSnapshot.checked_at.desc())
        .first()
    )


def _deviation_pct(my_price: float, reference: float) -> float | None:
    if reference == 0:
        return None
    return round((my_price - reference) / reference * 100, 1)


def _collect_price_rows(db: Session) -> list[dict]:
    """Собрать строки: категория + конкурент + цена."""
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

    rows: list[dict] = []
    for product in products:
        category = product.category
        if not category:
            continue
        snapshot = _latest_snapshot(db, product.id)
        if not snapshot:
            continue
        rows.append(
            {
                "category_id": category.id,
                "category_name": category.name,
                "my_price": float(category.my_price),
                "competitor_id": product.competitor_id,
                "competitor_name": product.competitor.name,
                "product_name": product.name,
                "price": float(snapshot.price),
                "checked_at": snapshot.checked_at,
            }
        )
    return rows


def _build_category_summaries(rows: list[dict]) -> list[dict]:
    """Агрегировать данные по категориям."""
    grouped: dict[int, dict] = {}

    for row in rows:
        cat_id = row["category_id"]
        if cat_id not in grouped:
            grouped[cat_id] = {
                "category_id": cat_id,
                "category_name": row["category_name"],
                "my_price": row["my_price"],
                "competitor_prices": {},
                "last_checked_at": None,
            }

        entry = grouped[cat_id]
        comp_id = row["competitor_id"]
        current = entry["competitor_prices"].get(comp_id)
        if current is None or row["price"] < current["price"]:
            entry["competitor_prices"][comp_id] = {
                "competitor_id": comp_id,
                "competitor_name": row["competitor_name"],
                "price": row["price"],
                "product_name": row["product_name"],
            }

        checked_at = row["checked_at"]
        if entry["last_checked_at"] is None or checked_at > entry["last_checked_at"]:
            entry["last_checked_at"] = checked_at

    summaries = []
    for entry in grouped.values():
        competitors = sorted(
            entry["competitor_prices"].values(), key=lambda x: x["price"]
        )
        prices = [c["price"] for c in competitors]
        my_price = entry["my_price"]
        avg_price = round(sum(prices) / len(prices), 2)
        deviation_pct = _deviation_pct(my_price, avg_price)

        summaries.append(
            {
                "category_id": entry["category_id"],
                "category_name": entry["category_name"],
                "my_price": my_price,
                "avg_price": avg_price,
                "min_price": min(prices),
                "max_price": max(prices),
                "competitor_count": len(competitors),
                "deviation_pct": deviation_pct,
                "deviation_abs_pct": abs(deviation_pct) if deviation_pct is not None else 0,
                "indicator_class": price_indicator_class(deviation_pct),
                "last_checked_at": entry["last_checked_at"],
                "competitors": competitors,
            }
        )

    return sorted(summaries, key=lambda x: x["deviation_abs_pct"], reverse=True)


def get_attention_categories(db: Session, limit: int = 5) -> list[dict]:
    """Категории, требующие внимания (по абсолютному отклонению от средней)."""
    rows = _collect_price_rows(db)
    summaries = _build_category_summaries(rows)
    return summaries[:limit]


def get_market_categories(db: Session) -> list[dict]:
    """Полный анализ по категориям для страницы «Анализ рынка»."""
    rows = _collect_price_rows(db)
    return _build_category_summaries(rows)


def get_competitor_summaries(db: Session) -> list[dict]:
    """Сводка по конкурентам."""
    rows = _collect_price_rows(db)
    categories = _build_category_summaries(rows)
    category_stats = {c["category_id"]: c for c in categories}

    grouped: dict[int, dict] = {}
    for row in rows:
        comp_id = row["competitor_id"]
        cat_id = row["category_id"]
        cat = category_stats.get(cat_id)
        if not cat:
            continue

        comp_price = row["price"]
        my_price = row["my_price"]
        deviation = _deviation_pct(comp_price, my_price)

        if comp_id not in grouped:
            grouped[comp_id] = {
                "competitor_id": comp_id,
                "competitor_name": row["competitor_name"],
                "category_ids": set(),
                "deviations": [],
                "last_checked_at": None,
            }

        entry = grouped[comp_id]
        entry["category_ids"].add(cat_id)
        if deviation is not None:
            entry["deviations"].append(deviation)

        checked_at = row["checked_at"]
        if entry["last_checked_at"] is None or checked_at > entry["last_checked_at"]:
            entry["last_checked_at"] = checked_at

    summaries = []
    for entry in grouped.values():
        deviations = entry["deviations"]
        summaries.append(
            {
                "competitor_id": entry["competitor_id"],
                "competitor_name": entry["competitor_name"],
                "category_count": len(entry["category_ids"]),
                "avg_deviation_pct": (
                    round(sum(deviations) / len(deviations), 1) if deviations else None
                ),
                "min_deviation_pct": min(deviations) if deviations else None,
                "max_deviation_pct": max(deviations) if deviations else None,
                "last_checked_at": entry["last_checked_at"],
            }
        )

    return sorted(summaries, key=lambda x: x["competitor_name"])


def get_competitor_detail(db: Session, competitor_id: int) -> dict | None:
    """Детализация по конкуренту: цены по категориям."""
    competitor = db.get(Competitor, competitor_id)
    if not competitor:
        return None

    rows = _collect_price_rows(db)
    categories = _build_category_summaries(rows)
    category_stats = {c["category_id"]: c for c in categories}

    grouped: dict[int, dict] = {}
    last_checked_at: datetime | None = None

    for row in rows:
        if row["competitor_id"] != competitor_id:
            continue

        cat_id = row["category_id"]
        cat = category_stats.get(cat_id)
        if not cat:
            continue

        current = grouped.get(cat_id)
        if current is None or row["price"] < current["competitor_price"]:
            grouped[cat_id] = {
                "category_id": cat_id,
                "category_name": row["category_name"],
                "my_price": row["my_price"],
                "competitor_price": row["price"],
                "diff": round(row["my_price"] - row["price"], 2),
                "market_avg": cat["avg_price"],
                "market_min": cat["min_price"],
                "market_max": cat["max_price"],
                "deviation_pct": _deviation_pct(row["my_price"], cat["avg_price"]),
                "indicator_class": price_indicator_class(
                    _deviation_pct(row["my_price"], cat["avg_price"])
                ),
            }

        checked_at = row["checked_at"]
        if last_checked_at is None or checked_at > last_checked_at:
            last_checked_at = checked_at

    category_rows = sorted(grouped.values(), key=lambda x: x["category_name"])

    return {
        "competitor": competitor,
        "categories": category_rows,
        "last_checked_at": last_checked_at,
    }
