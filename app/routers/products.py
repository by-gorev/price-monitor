"""
Управление рыночными категориями и товарами конкурентов.
"""
from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.competitor import Competitor
from app.models.enums import MatchStatus
from app.models.product import CompetitorProduct, ProductCategory

router = APIRouter(prefix="/products")
templates = Jinja2Templates(directory="app/templates")

IGNORED_CATEGORY_VALUE = "__ignored__"

MATCH_STATUS_LABELS = {
    MatchStatus.UNMATCHED: "Без категории",
    MatchStatus.AUTO_MATCHED: "Авто",
    MatchStatus.MANUAL_MATCHED: "Вручную",
    MatchStatus.IGNORED: "Не учитывать",
}

PRODUCT_FILTERS = {
    "all": "Все",
    "unmatched": "Без категории",
    "manual": "Изменённые вручную",
    "ignored": "Не учитываемые",
}


def _apply_product_filter(query, filter_key: str):
    if filter_key == "unmatched":
        return query.filter(CompetitorProduct.match_status == MatchStatus.UNMATCHED)
    if filter_key == "manual":
        return query.filter(CompetitorProduct.manual_override.is_(True))
    if filter_key == "ignored":
        return query.filter(CompetitorProduct.match_status == MatchStatus.IGNORED)
    return query


@router.get("/", response_class=HTMLResponse)
def list_products(
    request: Request,
    filter: str = Query("all", alias="filter"),
    db: Session = Depends(get_db),
):
    """Страница управления категориями и товарами конкурентов."""
    filter_key = filter if filter in PRODUCT_FILTERS else "all"

    categories = db.query(ProductCategory).order_by(ProductCategory.name).all()
    competitors = db.query(Competitor).order_by(Competitor.name).all()

    query = (
        db.query(CompetitorProduct)
        .options(
            joinedload(CompetitorProduct.competitor),
            joinedload(CompetitorProduct.category),
            joinedload(CompetitorProduct.auto_category),
        )
        .order_by(CompetitorProduct.competitor_id, CompetitorProduct.name)
    )
    competitor_products = _apply_product_filter(query, filter_key).all()

    return templates.TemplateResponse(
        request=request,
        name="products.html",
        context={
            "categories": categories,
            "competitors": competitors,
            "competitor_products": competitor_products,
            "match_statuses": MatchStatus,
            "match_status_labels": MATCH_STATUS_LABELS,
            "product_filters": PRODUCT_FILTERS,
            "current_filter": filter_key,
            "ignored_value": IGNORED_CATEGORY_VALUE,
        },
    )


@router.post("/category/update")
def update_category(
    category_id: int = Form(...),
    my_price: float = Form(...),
    keywords: str = Form(""),
    db: Session = Depends(get_db),
):
    """Обновить цену и ключевые слова категории."""
    category = db.get(ProductCategory, category_id)
    if not category:
        raise ValueError("Категория не найдена")
    category.my_price = my_price
    category.keywords = keywords.strip() or None
    db.commit()
    return RedirectResponse(url="/products", status_code=303)


@router.post("/competitor/{product_id}/category")
def update_competitor_product_category(
    product_id: int,
    category_value: str = Form(""),
    filter: str = Form("all"),
    db: Session = Depends(get_db),
):
    """Назначить категорию товару конкурента вручную."""
    product = db.get(CompetitorProduct, product_id)
    if not product:
        raise ValueError("Товар не найден")

    value = category_value.strip()
    if value == IGNORED_CATEGORY_VALUE:
        product.category_id = None
        product.match_status = MatchStatus.IGNORED
        product.manual_override = True
    elif value:
        cat_id = int(value)
        category = db.get(ProductCategory, cat_id)
        if not category:
            raise ValueError("Категория не найдена")
        product.category_id = cat_id
        product.match_status = MatchStatus.MANUAL_MATCHED
        product.manual_override = True
    else:
        product.category_id = None
        product.match_status = MatchStatus.UNMATCHED
        product.manual_override = True

    db.commit()
    redirect_filter = filter if filter in PRODUCT_FILTERS else "all"
    return RedirectResponse(
        url=f"/products?filter={redirect_filter}",
        status_code=303,
    )


@router.post("/competitor/add")
def add_competitor_product(
    competitor_id: int = Form(...),
    name: str = Form(...),
    url: str = Form(""),
    category_id: str = Form(""),
    db: Session = Depends(get_db),
):
    """Добавить ссылку конкурента на товар."""
    raw = category_id.strip()
    if raw == IGNORED_CATEGORY_VALUE:
        cat_id = None
        status = MatchStatus.IGNORED
        manual = True
    elif raw:
        cat_id = int(raw)
        status = MatchStatus.MANUAL_MATCHED
        manual = True
    else:
        cat_id = None
        status = MatchStatus.UNMATCHED
        manual = False

    product = CompetitorProduct(
        competitor_id=competitor_id,
        name=name.strip(),
        url=url.strip() if url else None,
        category_id=cat_id,
        auto_category_id=None,
        match_status=status,
        manual_override=manual,
    )
    db.add(product)
    db.commit()
    return RedirectResponse(url="/products", status_code=303)
