"""
Проверка цен и история изменений.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.dashboard import (
    get_category_comparison_detail,
    get_category_comparisons,
    get_price_history,
)
from app.services.price_checker import check_delivery, check_prices

router = APIRouter(prefix="/prices")
templates = Jinja2Templates(directory="app/templates")


@router.post("/check")
def run_price_check(db: Session = Depends(get_db)):
    """Кнопка «Проверить цены» — запуск проверки."""
    check_prices(db)
    return RedirectResponse(url="/", status_code=303)


@router.post("/check-delivery")
def run_delivery_check(db: Session = Depends(get_db)):
    """Проверить условия доставки конкурентов."""
    check_delivery(db)
    return RedirectResponse(url="/delivery", status_code=303)


@router.get("/compare", response_class=HTMLResponse)
def price_comparison(request: Request, db: Session = Depends(get_db)):
    """Страница сравнения цен по рыночным категориям."""
    comparisons = get_category_comparisons(db)
    return templates.TemplateResponse(
        request=request,
        name="comparison.html",
        context={"comparisons": comparisons},
    )


@router.get("/categories/{category_id}", response_class=HTMLResponse)
def category_comparison_detail(
    request: Request,
    category_id: int,
    db: Session = Depends(get_db),
):
    """Детали категории — список товаров конкурентов."""
    detail = get_category_comparison_detail(db, category_id)
    if not detail:
        return RedirectResponse(url="/prices/compare", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="category_detail.html",
        context=detail,
    )


@router.get("/history", response_class=HTMLResponse)
def price_history(request: Request, db: Session = Depends(get_db)):
    """Страница истории изменений цен."""
    history = get_price_history(db)
    return templates.TemplateResponse(
        request=request,
        name="price_history.html",
        context={"history": history},
    )
