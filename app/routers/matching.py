"""
Страница сопоставления товаров конкурентов с нашими.
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.enums import MatchStatus, MatchType
from app.models.product import CompetitorProduct, MyProduct
from app.services.matching import (
    auto_match_products,
    confirm_match,
    get_suggested_match,
    ignore_product,
)

router = APIRouter(prefix="/matching")
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def matching_page(request: Request, db: Session = Depends(get_db)):
    """
    Список несопоставленных товаров конкурентов
    с предполагаемым нашим товаром.
    """
    unmatched = (
        db.query(CompetitorProduct)
        .options(joinedload(CompetitorProduct.competitor))
        .filter(CompetitorProduct.match_status == MatchStatus.UNMATCHED)
        .order_by(CompetitorProduct.name)
        .all()
    )

    # Для каждого товара — предполагаемое сопоставление
    suggestions = []
    for product in unmatched:
        suggested, score = get_suggested_match(db, product)
        suggestions.append(
            {
                "competitor_product": product,
                "suggested_product": suggested,
                "confidence_score": round(score * 100, 1) if suggested else 0,
            }
        )

    my_products = db.query(MyProduct).order_by(MyProduct.name).all()

    return templates.TemplateResponse(
        request=request,
        name="matching.html",
        context={
            "suggestions": suggestions,
            "my_products": my_products,
        },
    )


@router.post("/confirm")
def confirm_matching(
    competitor_product_id: int = Form(...),
    my_product_id: int = Form(...),
    db: Session = Depends(get_db),
):
    """Подтвердить предложенное сопоставление."""
    confirm_match(
        db,
        competitor_product_id=competitor_product_id,
        my_product_id=my_product_id,
        match_type=MatchType.MANUAL,
    )
    return RedirectResponse(url="/matching", status_code=303)


@router.post("/manual")
def manual_matching(
    competitor_product_id: int = Form(...),
    my_product_id: int = Form(...),
    db: Session = Depends(get_db),
):
    """Выбрать сопоставление вручную из списка."""
    confirm_match(
        db,
        competitor_product_id=competitor_product_id,
        my_product_id=my_product_id,
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
    """Запустить автоматическое сопоставление по названиям."""
    auto_match_products(db)
    return RedirectResponse(url="/matching", status_code=303)
