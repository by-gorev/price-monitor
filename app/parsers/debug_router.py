"""
Страница диагностики парсеров /parser-debug
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.parsers.debug_store import get_last_scan_summary, get_scan_history

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/parser-debug", response_class=HTMLResponse)
def parser_debug_page(request: Request):
    """Диагностика последних запусков парсеров."""
    return templates.TemplateResponse(
        request=request,
        name="parser_debug.html",
        context={
            "history": get_scan_history(limit=20),
            "last_summary": get_last_scan_summary(),
        },
    )
