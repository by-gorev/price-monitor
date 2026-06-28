"""
Управление рыночными категориями и товарами конкурентов.
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.competitor import Competitor
from app.models.enums import MatchStatus
from app.models.product import CompetitorProduct, ProductCategory

router = APIRouter(prefix="/products")
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def list_products(request: Request, db: Session = Depends(get_db)):
    """Страница управления категориями и товарами конкурентов."""
    categories = db.query(ProductCategory).order_by(ProductCategory.name).all()
    competitors = db.query(Competitor).order_by(Competitor.name).all()
    competitor_products = (
        db.query(CompetitorProduct)
        .options(
            joinedload(CompetitorProduct.competitor),
            joinedload(CompetitorProduct.category),
        )
        .order_by(CompetitorProduct.name)
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="products.html",
        context={
            "categories": categories,
            "competitors": competitors,
            "competitor_products": competitor_products,
            "match_statuses": MatchStatus,
        },
    )


@router.post("/category/add")
def add_category(
    name: str = Form(...),
    my_price: float = Form(0),
    keywords: str = Form(""),
    db: Session = Depends(get_db),
):
    """Добавить рыночную категорию."""
    category = ProductCategory(
        name=name.strip(),
        my_price=my_price,
        keywords=keywords.strip() or None,
    )
    db.add(category)
    db.commit()
    return RedirectResponse(url="/products", status_code=303)


@router.post("/category/keywords")
def update_category_keywords(
    category_id: int = Form(...),
    keywords: str = Form(""),
    db: Session = Depends(get_db),
):
    """Обновить ключевые слова категории."""
    category = db.get(ProductCategory, category_id)
    if not category:
        raise ValueError("Категория не найдена")
    category.keywords = keywords.strip() or None
    db.commit()
    return RedirectResponse(url="/products", status_code=303)


@router.post("/competitor/add")
def add_competitor_product(
    competitor_id: int = Form(...),
    name: str = Form(...),
    url: str = Form(""),
    category_id: str = Form(""),
    db: Session = Depends(get_db),
):
    """Добавить ссылку конкурента на товар."""
    cat_id = int(category_id) if category_id else None
    product = CompetitorProduct(
        competitor_id=competitor_id,
        name=name.strip(),
        url=url.strip() if url else None,
        category_id=cat_id,
        match_status=(
            MatchStatus.MANUAL_MATCHED if cat_id else MatchStatus.UNMATCHED
        ),
    )
    db.add(product)
    db.commit()
    return RedirectResponse(url="/products", status_code=303)
