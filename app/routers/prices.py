"""
Проверка цен и история изменений.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.dashboard import get_price_history
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


@router.get("/history", response_class=HTMLResponse)
def price_history(request: Request, db: Session = Depends(get_db)):
    """Страница истории изменений цен."""
    history = get_price_history(db)
    return templates.TemplateResponse(
        request=request,
        name="price_history.html",
        context={"history": history},
    )
