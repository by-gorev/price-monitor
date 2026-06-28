"""
Страница анализа рынка.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.market_analysis import (
    get_competitor_detail,
    get_competitor_summaries,
    get_market_categories,
)

router = APIRouter(prefix="/market")
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def market_page(request: Request, db: Session = Depends(get_db)):
    """Анализ рынка: категории и конкуренты."""
    return templates.TemplateResponse(
        request=request,
        name="market.html",
        context={
            "categories": get_market_categories(db),
            "competitors": get_competitor_summaries(db),
        },
    )


@router.get("/competitors/{competitor_id}", response_class=HTMLResponse)
def competitor_detail_page(
    request: Request,
    competitor_id: int,
    db: Session = Depends(get_db),
):
    """Детализация по выбранному конкуренту."""
    detail = get_competitor_detail(db, competitor_id)
    if not detail:
        return RedirectResponse(url="/market", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="market_competitor.html",
        context=detail,
    )
