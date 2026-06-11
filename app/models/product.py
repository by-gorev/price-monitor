"""
Модели товаров, сопоставлений и снимков цен.
"""
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import MatchStatus, MatchType


class ProductCategory(Base):
    """Категория товаров (например: латексные шары, фольгированные)."""

    __tablename__ = "product_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    my_products: Mapped[list["MyProduct"]] = relationship(back_populates="category")
    competitor_products: Mapped[list["CompetitorProduct"]] = relationship(
        back_populates="category"
    )


class MyProduct(Base):
    """Наш эталонный товар — к нему привязываются товары конкурентов."""

    __tablename__ = "my_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_categories.id"), nullable=True
    )
    my_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)

    category: Mapped["ProductCategory | None"] = relationship(back_populates="my_products")
    matches: Mapped[list["ProductMatch"]] = relationship(back_populates="my_product")


class CompetitorProduct(Base):
    """Товар конкурента на его сайте."""

    __tablename__ = "competitor_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id"), nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_categories.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # JSON-строка с настройками CSS-селекторов для парсинга (добавим позже)
    selector_config: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, name="match_status_enum"),
        nullable=False,
        default=MatchStatus.UNMATCHED,
    )

    competitor: Mapped["Competitor"] = relationship(back_populates="products")
    category: Mapped["ProductCategory | None"] = relationship(
        back_populates="competitor_products"
    )
    matches: Mapped[list["ProductMatch"]] = relationship(
        back_populates="competitor_product"
    )
    price_snapshots: Mapped[list["PriceSnapshot"]] = relationship(
        back_populates="competitor_product"
    )


class ProductMatch(Base):
    """Связь между нашим товаром и товаром конкурента."""

    __tablename__ = "product_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    my_product_id: Mapped[int] = mapped_column(ForeignKey("my_products.id"), nullable=False)
    competitor_product_id: Mapped[int] = mapped_column(
        ForeignKey("competitor_products.id"), nullable=False, unique=True
    )
    match_type: Mapped[MatchType] = mapped_column(
        Enum(MatchType, name="match_type_enum"), nullable=False
    )
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    my_product: Mapped["MyProduct"] = relationship(back_populates="matches")
    competitor_product: Mapped["CompetitorProduct"] = relationship(
        back_populates="matches"
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
