"""
Модели конкурентов и снимков доставки.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Competitor(Base):
    """Конкурент — магазин воздушных шаров."""

    __tablename__ = "competitors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    website_url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Связи
    products: Mapped[list["CompetitorProduct"]] = relationship(
        back_populates="competitor"
    )
    delivery_snapshots: Mapped[list["DeliverySnapshot"]] = relationship(
        back_populates="competitor"
    )


class DeliverySnapshot(Base):
    """Снимок условий и цены доставки конкурента на момент проверки."""

    __tablename__ = "delivery_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id"), nullable=False)
    delivery_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    competitor: Mapped["Competitor"] = relationship(back_populates="delivery_snapshots")
