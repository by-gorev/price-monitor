"""
Страница назначения рыночных категорий товарам конкурентов.
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.enums import MatchStatus, MatchType
from app.models.product import CompetitorProduct, ProductCategory
from app.services.matching import (
    auto_match_products,
    confirm_category,
    get_suggested_category,
    ignore_product,
)

router = APIRouter(prefix="/matching")
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def matching_page(request: Request, db: Session = Depends(get_db)):
    """Товары конкурентов без назначенной категории."""
    unmatched = (
        db.query(CompetitorProduct)
        .options(joinedload(CompetitorProduct.competitor))
        .filter(CompetitorProduct.match_status == MatchStatus.UNMATCHED)
        .order_by(CompetitorProduct.name)
        .all()
    )

    suggestions = []
    for product in unmatched:
        suggested, score = get_suggested_category(db, product)
        suggestions.append(
            {
                "competitor_product": product,
                "suggested_category": suggested,
                "confidence_score": round(score * 100, 1) if suggested else 0,
            }
        )

    categories = db.query(ProductCategory).order_by(ProductCategory.name).all()

    return templates.TemplateResponse(
        request=request,
        name="matching.html",
        context={
            "suggestions": suggestions,
            "categories": categories,
        },
    )


@router.post("/confirm")
def confirm_matching(
    competitor_product_id: int = Form(...),
    category_id: int = Form(...),
    db: Session = Depends(get_db),
):
    """Подтвердить предложенную категорию."""
    confirm_category(
        db,
        competitor_product_id=competitor_product_id,
        category_id=category_id,
        match_type=MatchType.MANUAL,
    )
    return RedirectResponse(url="/matching", status_code=303)


@router.post("/manual")
def manual_matching(
    competitor_product_id: int = Form(...),
    category_id: int = Form(...),
    db: Session = Depends(get_db),
):
    """Выбрать категорию вручную."""
    confirm_category(
        db,
        competitor_product_id=competitor_product_id,
        category_id=category_id,
        match_type=MatchType.MANUAL,
    )
    return RedirectResponse(url="/matching", status_code=303)


@router.post("/ignore")
def ignore_matching(
    competitor_product_id: int = Form(...),
    db: Session = Depends(get_db),
):
    """Игнорировать товар конкурента."""
    ignore_product(db, competitor_product_id)
    return RedirectResponse(url="/matching", status_code=303)


@router.post("/auto")
def run_auto_matching(db: Session = Depends(get_db)):
    """Запустить автоматическое назначение категорий."""
    auto_match_products(db)
    return RedirectResponse(url="/matching", status_code=303)
