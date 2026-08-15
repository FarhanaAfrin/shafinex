"""ORM models.

Design note: nothing about the *content* of the tracker is hardcoded. Sheets,
categories and net-worth items are all rows, so the user can rename, recolor,
reorder, add and remove anything from the UI. Only the shape (category x month
x kind) is fixed.
"""

from typing import Optional

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Sheet(Base, TimestampMixin):
    """A user-defined tab, e.g. Income or Expenditure. `kind` tells the maths
    which direction money moves so custom sheets still aggregate correctly."""

    __tablename__ = "sheet"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # 'inflow' | 'outflow'
    icon: Mapped[str] = mapped_column(String(64), default="mdi-table", nullable=False)
    color: Mapped[str] = mapped_column(String(9), default="#6366F1", nullable=False)
    plan_label: Mapped[str] = mapped_column(String(64), default="Planned", nullable=False)
    show_plan: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    categories: Mapped[list["Category"]] = relationship(
        back_populates="sheet", cascade="all, delete-orphan", order_by="Category.sort_order"
    )


class Category(Base, TimestampMixin):
    __tablename__ = "category"
    __table_args__ = (UniqueConstraint("sheet_id", "name", name="uq_category_sheet_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sheet_id: Mapped[int] = mapped_column(
        ForeignKey("sheet.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    group_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(9), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sheet: Mapped[Sheet] = relationship(back_populates="categories")
    values: Mapped[list["MonthlyValue"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class MonthlyValue(Base, TimestampMixin):
    """One cell. kind='plan' is the budget/expected column, 'actual' is a month."""

    __tablename__ = "monthly_value"
    __table_args__ = (
        UniqueConstraint("category_id", "year", "month", "kind", name="uq_monthly_value_cell"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("category.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # month 0 is reserved for the plan column (which is per-year, not per-month).
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # 'plan' | 'actual'
    amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)

    category: Mapped[Category] = relationship(back_populates="values")


class NetworthItem(Base, TimestampMixin):
    __tablename__ = "networth_item"
    __table_args__ = (UniqueConstraint("side", "name", name="uq_networth_item_side_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    side: Mapped[str] = mapped_column(String(16), nullable=False)  # 'asset' | 'liability'
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[Optional[str]] = mapped_column(String(9), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    values: Mapped[list["NetworthValue"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class NetworthValue(Base, TimestampMixin):
    __tablename__ = "networth_value"
    __table_args__ = (UniqueConstraint("item_id", "year", "month", name="uq_networth_value_cell"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("networth_item.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)

    item: Mapped[NetworthItem] = relationship(back_populates="values")


class Tool(Base, TimestampMixin):
    """The workbook's Tools tab: cards, apps and services you use, with the
    referral bonus and link/code attached to each."""

    __tablename__ = "tool"
    __table_args__ = (UniqueConstraint("name", name="uq_tool_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    purpose: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    bonus: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)  # "100", "$30-40", "50% off"
    link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # URL or a plain referral code
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Setting(Base, TimestampMixin):
    """Free-form preference store: appearance, currency, goals, defaults."""

    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
