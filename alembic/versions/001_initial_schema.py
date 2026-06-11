"""Начальная схема базы данных

Revision ID: 001
Revises:
Create Date: 2026-06-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Таблица конкурентов
    op.create_table(
        "competitors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("website_url", sa.String(length=500), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Категории товаров
    op.create_table(
        "product_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Наши эталонные товары
    op.create_table(
        "my_products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("my_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["product_categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Товары конкурентов
    op.create_table(
        "competitor_products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competitor_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("selector_config", sa.Text(), nullable=True),
        sa.Column(
            "match_status",
            sa.Enum(
                "UNMATCHED",
                "AUTO_MATCHED",
                "MANUAL_MATCHED",
                "IGNORED",
                name="match_status_enum",
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["category_id"], ["product_categories.id"]),
        sa.ForeignKeyConstraint(["competitor_id"], ["competitors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Сопоставления товаров
    op.create_table(
        "product_matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("my_product_id", sa.Integer(), nullable=False),
        sa.Column("competitor_product_id", sa.Integer(), nullable=False),
        sa.Column(
            "match_type",
            sa.Enum("AUTO", "MANUAL", name="match_type_enum"),
            nullable=False,
        ),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.ForeignKeyConstraint(["competitor_product_id"], ["competitor_products.id"]),
        sa.ForeignKeyConstraint(["my_product_id"], ["my_products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("competitor_product_id"),
    )

    # Снимки цен
    op.create_table(
        "price_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competitor_product_id", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["competitor_product_id"], ["competitor_products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Снимки доставки
    op.create_table(
        "delivery_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competitor_id", sa.Integer(), nullable=False),
        sa.Column("delivery_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["competitor_id"], ["competitors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("delivery_snapshots")
    op.drop_table("price_snapshots")
    op.drop_table("product_matches")
    op.drop_table("competitor_products")
    op.drop_table("my_products")
    op.drop_table("product_categories")
    op.drop_table("competitors")
    op.execute("DROP TYPE IF EXISTS match_type_enum")
    op.execute("DROP TYPE IF EXISTS match_status_enum")
