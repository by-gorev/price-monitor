"""
Главная страница — dashboard со статистикой.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.dashboard import get_dashboard_stats

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    """Главная страница с ключевыми показателями."""
    stats = get_dashboard_stats(db)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"stats": stats},
    )
