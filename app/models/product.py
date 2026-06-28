"""
Модели товаров, категорий и снимков цен.
"""
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import MatchStatus


class ProductCategory(Base):
    """Рыночная категория — единица сравнения цен."""

    __tablename__ = "product_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # Наша ориентировочная цена по категории
    my_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    # Ключевые слова через запятую для авто-сопоставления
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)

    competitor_products: Mapped[list["CompetitorProduct"]] = relationship(
        back_populates="category"
    )


class CompetitorProduct(Base):
    """Товар или позиция конкурента на его сайте."""

    __tablename__ = "competitor_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id"), nullable=False)
    # Привязка к рыночной категории (основная связь вместо ProductMatch)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_categories.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    selector_config: Mapped[str | None] = mapped_column(Text, nullable=True)
    # UNMATCHED — категория не назначена; AUTO_/MANUAL_MATCHED — категория назначена
    match_status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, name="match_status_enum"),
        nullable=False,
        default=MatchStatus.UNMATCHED,
    )

    competitor: Mapped["Competitor"] = relationship(back_populates="products")
    category: Mapped["ProductCategory | None"] = relationship(
        back_populates="competitor_products"
    )
    price_snapshots: Mapped[list["PriceSnapshot"]] = relationship(
        back_populates="competitor_product"
    )


class PriceSnapshot(Base):
    """Снимок цены товара конкурента на момент проверки."""

    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    competitor_product_id: Mapped[int] = mapped_column(
        ForeignKey("competitor_products.id"), nullable=False
    )
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    competitor_product: Mapped["CompetitorProduct"] = relationship(
        back_populates="price_snapshots"
    )
