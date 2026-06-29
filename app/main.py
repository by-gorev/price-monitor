"""
Точка входа FastAPI-приложения competitor-monitor.
Мониторинг цен конкурентов на воздушные шары.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.parsers.debug_router import router as parser_debug_router
from app.routers import (
    competitor_categories,
    competitors,
    dashboard,
    delivery,
    market,
    matching,
    prices,
    products,
)

app = FastAPI(
    title="Competitor Monitor",
    description="Мониторинг цен конкурентов на воздушные шары",
    version="0.1.0",
)

# Подключаем роутеры
app.include_router(dashboard.router)
app.include_router(competitor_categories.router)
app.include_router(competitors.router)
app.include_router(products.router)
app.include_router(matching.router)
app.include_router(market.router)
app.include_router(prices.router)
app.include_router(delivery.router)
app.include_router(parser_debug_router)

# Статические файлы (CSS)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
