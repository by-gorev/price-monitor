"""
Модели конкурентов и снимков доставки.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Competitor(Base):
    """Конкурент — магазин воздушных шаров."""

    __tablename__ = "competitors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    website_url: Mapped[str] = mapped_column(String(500), nullable=False)

    products: Mapped[list["CompetitorProduct"]] = relationship(
        back_populates="competitor"
    )
    delivery_snapshots: Mapped[list["DeliverySnapshot"]] = relationship(
        back_populates="competitor"
    )
    competitor_categories: Mapped[list["CompetitorCategory"]] = relationship(
        back_populates="competitor"
    )


class CompetitorCategory(Base):
    """URL страницы категории конкурента, привязанной к рыночной категории."""

    __tablename__ = "competitor_categories"
    __table_args__ = (
        UniqueConstraint("competitor_id", "product_category_id", name="uq_competitor_market_category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id"), nullable=False)
    product_category_id: Mapped[int] = mapped_column(
        ForeignKey("product_categories.id"), nullable=False
    )
    category_url: Mapped[str] = mapped_column(String(1000), nullable=False)

    competitor: Mapped["Competitor"] = relationship(back_populates="competitor_categories")
    product_category: Mapped["ProductCategory"] = relationship(
        back_populates="competitor_categories"
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


from app.models.product import CompetitorProduct, ProductCategory  # noqa: E402
