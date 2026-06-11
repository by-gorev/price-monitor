"""
Управление конкурентами.
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.competitor import Competitor

router = APIRouter(prefix="/competitors")
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def list_competitors(request: Request, db: Session = Depends(get_db)):
    """Список конкурентов."""
    competitors = db.query(Competitor).order_by(Competitor.name).all()
    return templates.TemplateResponse(
        request=request,
        name="competitors.html",
        context={"competitors": competitors},
    )


@router.post("/add")
def add_competitor(
    name: str = Form(...),
    website_url: str = Form(...),
    db: Session = Depends(get_db),
):
    """Добавить нового конкурента вручную."""
    competitor = Competitor(name=name.strip(), website_url=website_url.strip())
    db.add(competitor)
    db.commit()
    return RedirectResponse(url="/competitors", status_code=303)
