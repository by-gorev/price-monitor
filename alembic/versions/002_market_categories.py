"""Переход на рыночные категории: my_price в категориях, удаление my_products и product_matches

Revision ID: 002
Revises: 001
Create Date: 2026-06-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Цена по категории вместо отдельной таблицы my_products
    op.add_column(
        "product_categories",
        sa.Column("my_price", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
    )

    # Переносим цены из my_products в категории (если данные уже есть)
    op.execute(
        """
        UPDATE product_categories pc
        SET my_price = sub.max_price
        FROM (
            SELECT category_id, MAX(my_price) AS max_price
            FROM my_products
            WHERE category_id IS NOT NULL
            GROUP BY category_id
        ) sub
        WHERE pc.id = sub.category_id
        """
    )

    op.drop_table("product_matches")
    op.drop_table("my_products")


def downgrade() -> None:
    op.create_table(
        "my_products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("my_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["product_categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
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
    op.drop_column("product_categories", "my_price")
