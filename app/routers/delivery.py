"""
Страница условий доставки конкурентов.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.competitor import DeliverySnapshot

router = APIRouter(prefix="/delivery")
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def delivery_page(request: Request, db: Session = Depends(get_db)):
    """
    Последние снимки доставки по каждому конкуренту.
    """
    # Берём последний снимок для каждого конкурента
    snapshots = (
        db.query(DeliverySnapshot)
        .options(joinedload(DeliverySnapshot.competitor))
        .order_by(DeliverySnapshot.checked_at.desc())
        .all()
    )

    # Оставляем только последний снимок на конкурента
    seen = set()
    latest = []
    for snap in snapshots:
        if snap.competitor_id not in seen:
            seen.add(snap.competitor_id)
            latest.append(snap)

    return templates.TemplateResponse(
        request=request,
        name="delivery.html",
        context={"snapshots": latest},
    )
