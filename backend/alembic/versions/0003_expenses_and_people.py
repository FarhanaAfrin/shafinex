"""expenses, people and splits

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "person",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("relation", sa.String(24), nullable=False, server_default="friend"),
        sa.Column("contact", sa.String(160), nullable=True),
        sa.Column("color", sa.String(9), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", name="uq_person_name"),
    )

    op.create_table(
        "expense",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("spent_on", sa.Date, nullable=False, index=True),
        sa.Column("merchant", sa.String(160), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column(
            "category_id",
            sa.Integer,
            sa.ForeignKey("category.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("total_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("my_share", sa.Numeric(16, 2), nullable=False),
        sa.Column("is_split", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("extraction", sa.JSON, nullable=True),
        sa.Column("applied_category_id", sa.Integer, nullable=True),
        sa.Column("applied_year", sa.Integer, nullable=True),
        sa.Column("applied_month", sa.Integer, nullable=True),
        sa.Column("applied_amount", sa.Numeric(16, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "expense_share",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "expense_id",
            sa.Integer,
            sa.ForeignKey("expense.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "person_id",
            sa.Integer,
            sa.ForeignKey("person.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("expense_id", "person_id", name="uq_share_expense_person"),
    )


def downgrade() -> None:
    op.drop_table("expense_share")
    op.drop_table("expense")
    op.drop_table("person")
