"""The editable grid: read a sheet as wide rows, write it back one cell at a time."""

from typing import Optional

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..auth import require_auth
from ..db import get_db
from ..models import Category, MonthlyValue, Sheet
from ..preferences import build_calendar, get_preferences
from ..schemas import (
    BulkValuePatch,
    GridResponse,
    GridRow,
    RowFillRequest,
    SheetOut,
    ValuePatch,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["grid"], dependencies=[Depends(require_auth)])
ZERO = Decimal("0")

# The plan column is stored as month=0 so one table covers both.
PLAN_MONTH = 0


def _load_sheet(db: Session, slug: str) -> Sheet:
    sheet = db.execute(select(Sheet).where(Sheet.slug == slug)).scalar_one_or_none()
    if sheet is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Sheet '{slug}' not found")
    return sheet


def _cell_map(db: Session, category_ids: list[int], months: list[dict], year: int) -> dict:
    """{(category_id, year, month, kind): amount} for the whole visible window."""
    if not category_ids:
        return {}
    year_span = sorted({m["year"] for m in months} | {year})
    rows = db.execute(
        select(MonthlyValue).where(
            MonthlyValue.category_id.in_(category_ids),
            MonthlyValue.year.in_(year_span),
        )
    ).scalars()
    return {(r.category_id, r.year, r.month, r.kind): Decimal(r.amount) for r in rows}


def _balance_row(db: Session, months: list[dict], year: int) -> tuple[list[Decimal], Decimal]:
    """The workbook's Balance row: money in minus money out, per column.

    Sums every active sheet by its kind, so it still means the same thing once
    the user has added sheets of their own.
    """
    year_span = sorted({m["year"] for m in months} | {year})
    rows = db.execute(
        select(Sheet.kind, MonthlyValue.year, MonthlyValue.month, MonthlyValue.kind, MonthlyValue.amount)
        .join(Category, Category.sheet_id == Sheet.id)
        .join(MonthlyValue, MonthlyValue.category_id == Category.id)
        .where(
            Sheet.is_active.is_(True),
            Category.is_active.is_(True),
            MonthlyValue.year.in_(year_span),
        )
    ).all()

    column_of = {(m["year"], m["month"]): m["index"] for m in months}
    balance = [ZERO] * 12
    plan_balance = ZERO

    for sheet_kind, value_year, month, value_kind, amount in rows:
        sign = 1 if sheet_kind == "inflow" else -1
        if value_kind == "plan":
            if value_year == year:
                plan_balance += sign * Decimal(amount)
            continue
        index = column_of.get((value_year, month))
        if index is not None:
            balance[index] += sign * Decimal(amount)

    return balance, plan_balance


@router.get("/grid", response_model=GridResponse)
def read_grid(
    sheet: str = Query(..., description="sheet slug"),
    year: int = Query(..., ge=1900, le=2999),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    sheet_row = _load_sheet(db, sheet)
    prefs = get_preferences(db)
    months = build_calendar(year, prefs)

    stmt = (
        select(Category)
        .where(Category.sheet_id == sheet_row.id)
        .order_by(Category.sort_order, Category.id)
    )
    if not include_inactive:
        stmt = stmt.where(Category.is_active.is_(True))
    categories = list(db.execute(stmt).scalars().all())
    cells = _cell_map(db, [c.id for c in categories], months, year)

    rows: list[GridRow] = []
    column_totals = [ZERO] * 12
    plan_total = ZERO

    for category in categories:
        plan = cells.get((category.id, year, PLAN_MONTH, "plan"))
        values: list[Optional[Decimal]] = []
        row_total = ZERO
        filled = 0
        for column in months:
            amount = cells.get((category.id, column["year"], column["month"], "actual"))
            values.append(amount)
            if amount is not None:
                row_total += amount
                filled += 1
                column_totals[column["index"]] += amount
        if plan is not None:
            plan_total += plan
        average = (row_total / filled) if filled else ZERO
        if plan is None:
            variance = None
        elif sheet_row.kind == "outflow":
            variance = plan - row_total  # positive = under budget
        else:
            variance = row_total - plan  # positive = ahead of plan
        rows.append(
            GridRow(
                category_id=category.id,
                name=category.name,
                group_name=category.group_name,
                color=category.color,
                note=category.note,
                is_active=category.is_active,
                plan=plan,
                cells=values,
                total=row_total,
                average=average,
                variance=variance,
            )
        )

    balance_row, balance_plan = (
        _balance_row(db, months, year) if sheet_row.kind == "outflow" else (None, None)
    )

    return GridResponse(
        sheet=SheetOut.model_validate(sheet_row),
        year=year,
        months=months,
        rows=rows,
        column_totals=column_totals,
        plan_total=plan_total,
        grand_total=sum(column_totals, ZERO),
        balance_row=balance_row,
        balance_plan=balance_plan,
    )


def _upsert(db: Session, patch: ValuePatch) -> None:
    if db.get(Category, patch.category_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    kind = "plan" if patch.month == PLAN_MONTH else patch.kind
    if kind == "plan" and patch.month != PLAN_MONTH:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Plan values use month=0")

    existing = db.execute(
        select(MonthlyValue).where(
            MonthlyValue.category_id == patch.category_id,
            MonthlyValue.year == patch.year,
            MonthlyValue.month == patch.month,
            MonthlyValue.kind == kind,
        )
    ).scalar_one_or_none()

    if patch.amount is None:
        if existing is not None:
            db.delete(existing)
        return
    if existing is None:
        db.add(
            MonthlyValue(
                category_id=patch.category_id,
                year=patch.year,
                month=patch.month,
                kind=kind,
                amount=patch.amount,
            )
        )
    else:
        existing.amount = patch.amount


@router.patch("/values", status_code=status.HTTP_200_OK)
def patch_value(patch: ValuePatch, db: Session = Depends(get_db)):
    _upsert(db, patch)
    db.commit()
    log.info(
        "value write category=%s %s-%s kind=%s amount=%s",
        patch.category_id, patch.year, patch.month, patch.kind, patch.amount,
    )
    return {"ok": True}


@router.patch("/values/bulk", status_code=status.HTTP_200_OK)
def patch_values_bulk(payload: BulkValuePatch, db: Session = Depends(get_db)):
    """All-or-nothing: one bad cell rolls the whole batch back."""
    for patch in payload.patches:
        _upsert(db, patch)
    db.commit()
    log.info("bulk write count=%s", len(payload.patches))
    return {"ok": True, "written": len(payload.patches)}


@router.post("/values/fill-row", status_code=status.HTTP_200_OK)
def fill_row(payload: RowFillRequest, db: Session = Depends(get_db)):
    """Set every remaining month of a row to one amount (or clear it).
    Handy for fixed costs like rent."""
    prefs = get_preferences(db)
    months = build_calendar(payload.year, prefs)
    patches = [
        ValuePatch(
            category_id=payload.category_id,
            year=column["year"],
            month=column["month"],
            kind="actual",
            amount=payload.amount,
        )
        for column in months
        if column["index"] >= payload.from_month - 1
    ]
    for patch in patches:
        _upsert(db, patch)
    db.commit()
    log.info("row fill category=%s year=%s amount=%s", payload.category_id, payload.year, payload.amount)
    return {"ok": True, "written": len(patches)}


@router.post("/values/copy-year", status_code=status.HTTP_200_OK)
def copy_year(
    source: int = Query(..., ge=1900, le=2999),
    target: int = Query(..., ge=1900, le=2999),
    plan_only: bool = True,
    overwrite: bool = False,
    db: Session = Depends(get_db),
):
    """Start a new year from the last one — plan columns by default."""
    if source == target:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Source and target years are the same")

    stmt = select(MonthlyValue).where(MonthlyValue.year == source)
    if plan_only:
        stmt = stmt.where(MonthlyValue.kind == "plan")
    source_rows = list(db.execute(stmt).scalars().all())

    existing = {
        (r.category_id, r.month, r.kind): r
        for r in db.execute(select(MonthlyValue).where(MonthlyValue.year == target)).scalars()
    }

    written = 0
    for row in source_rows:
        key = (row.category_id, row.month, row.kind)
        if key in existing:
            if not overwrite:
                continue
            existing[key].amount = row.amount
        else:
            db.add(
                MonthlyValue(
                    category_id=row.category_id,
                    year=target,
                    month=row.month,
                    kind=row.kind,
                    amount=row.amount,
                )
            )
        written += 1
    db.commit()
    log.info("copy year %s->%s written=%s plan_only=%s", source, target, written, plan_only)
    return {"ok": True, "written": written}


@router.delete("/values/year", status_code=status.HTTP_200_OK)
def clear_year(
    year: int = Query(..., ge=1900, le=2999),
    sheet: Optional[str] = None,
    db: Session = Depends(get_db),
):
    stmt = delete(MonthlyValue).where(MonthlyValue.year == year)
    if sheet:
        sheet_row = _load_sheet(db, sheet)
        category_ids = select(Category.id).where(Category.sheet_id == sheet_row.id)
        stmt = stmt.where(MonthlyValue.category_id.in_(category_ids))
    result = db.execute(stmt)
    db.commit()
    log.warning("cleared year=%s sheet=%s rows=%s", year, sheet, result.rowcount)
    return {"ok": True, "deleted": result.rowcount}
