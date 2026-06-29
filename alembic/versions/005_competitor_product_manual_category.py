"""manual_override и auto_category_id для товаров конкурентов

Revision ID: 005
Revises: 004
Create Date: 2026-06-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "competitor_products",
        sa.Column(
            "manual_override",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "competitor_products",
        sa.Column("auto_category_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_competitor_products_auto_category_id",
        "competitor_products",
        "product_categories",
        ["auto_category_id"],
        ["id"],
    )
    op.execute(
        """
        UPDATE competitor_products
        SET auto_category_id = category_id
        WHERE match_status = 'AUTO_MATCHED' AND category_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE competitor_products
        SET manual_override = TRUE
        WHERE match_status IN ('MANUAL_MATCHED', 'IGNORED')
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_competitor_products_auto_category_id",
        "competitor_products",
        type_="foreignkey",
    )
    op.drop_column("competitor_products", "auto_category_id")
    op.drop_column("competitor_products", "manual_override")
