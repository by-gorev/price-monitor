"""
Управление URL категорий конкурентов и сканирование товаров.
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.competitor import Competitor, CompetitorCategory
from app.models.product import ProductCategory
from app.services.scanner_service import scan_category

router = APIRouter(prefix="/competitor-categories")
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def competitor_categories_page(request: Request, db: Session = Depends(get_db)):
    """Страница привязки URL категорий конкурента к рыночным категориям."""
    entries = (
        db.query(CompetitorCategory)
        .options(
            joinedload(CompetitorCategory.competitor),
            joinedload(CompetitorCategory.product_category),
        )
        .order_by(CompetitorCategory.id)
        .all()
    )
    competitors = db.query(Competitor).order_by(Competitor.name).all()
    categories = db.query(ProductCategory).order_by(ProductCategory.name).all()

    return templates.TemplateResponse(
        request=request,
        name="competitor_categories.html",
        context={
            "entries": entries,
            "competitors": competitors,
            "categories": categories,
        },
    )


@router.post("/add")
def add_competitor_category(
    competitor_id: int = Form(...),
    product_category_id: int = Form(...),
    category_url: str = Form(...),
    db: Session = Depends(get_db),
):
    """Добавить или обновить URL страницы категории конкурента."""
    existing = (
        db.query(CompetitorCategory)
        .filter(
            CompetitorCategory.competitor_id == competitor_id,
            CompetitorCategory.product_category_id == product_category_id,
        )
        .first()
    )
    if existing:
        existing.category_url = category_url.strip()
    else:
        db.add(
            CompetitorCategory(
                competitor_id=competitor_id,
                product_category_id=product_category_id,
                category_url=category_url.strip(),
            )
        )
    db.commit()
    return RedirectResponse(url="/competitor-categories", status_code=303)


@router.post("/scan")
def run_scan(
    competitor_category_id: int = Form(...),
    db: Session = Depends(get_db),
):
    """Сканировать одну категорию конкурента и обновить цены."""
    scan_category(db, competitor_category_id)
    return RedirectResponse(url="/competitor-categories", status_code=303)
