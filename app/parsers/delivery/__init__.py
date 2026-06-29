"""Парсеры доставки (архитектура, реализации — позже)."""
from app.parsers.delivery.base import (
    BaseDeliveryParser,
    DeliveryInfo,
    DeliveryParserRegistry,
    delivery_registry,
)

__all__ = [
    "BaseDeliveryParser",
    "DeliveryInfo",
    "DeliveryParserRegistry",
    "delivery_registry",
]
