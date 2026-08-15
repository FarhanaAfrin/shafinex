"""initial schema

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sheet",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("icon", sa.String(64), nullable=False, server_default="mdi-table"),
        sa.Column("color", sa.String(9), nullable=False, server_default="#6366F1"),
        sa.Column("plan_label", sa.String(64), nullable=False, server_default="Planned"),
        sa.Column("show_plan", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "category",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "sheet_id",
            sa.Integer,
            sa.ForeignKey("sheet.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("group_name", sa.String(120), nullable=True),
        sa.Column("color", sa.String(9), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("sheet_id", "name", name="uq_category_sheet_name"),
    )

    op.create_table(
        "monthly_value",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "category_id",
            sa.Integer,
            sa.ForeignKey("category.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("year", sa.Integer, nullable=False, index=True),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("category_id", "year", "month", "kind", name="uq_monthly_value_cell"),
    )

    op.create_table(
        "networth_item",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("side", sa.String(16), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("color", sa.String(9), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("side", "name", name="uq_networth_item_side_name"),
    )

    op.create_table(
        "networth_value",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "item_id",
            sa.Integer,
            sa.ForeignKey("networth_item.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("year", sa.Integer, nullable=False, index=True),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("item_id", "year", "month", name="uq_networth_value_cell"),
    )

    op.create_table(
        "app_setting",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_setting")
    op.drop_table("networth_value")
    op.drop_table("networth_item")
    op.drop_table("monthly_value")
    op.drop_table("category")
    op.drop_table("sheet")
