"""Таблица competitor_categories

Revision ID: 004
Revises: 003
Create Date: 2026-06-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "competitor_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competitor_id", sa.Integer(), nullable=False),
        sa.Column("product_category_id", sa.Integer(), nullable=False),
        sa.Column("category_url", sa.String(length=1000), nullable=False),
        sa.ForeignKeyConstraint(["competitor_id"], ["competitors.id"]),
        sa.ForeignKeyConstraint(["product_category_id"], ["product_categories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "competitor_id", "product_category_id", name="uq_competitor_market_category"
        ),
    )


def downgrade() -> None:
    op.drop_table("competitor_categories")
