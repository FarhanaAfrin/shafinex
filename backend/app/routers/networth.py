"""Net worth grid: assets and liabilities as month-end balances."""

from typing import Optional

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_auth
from ..db import get_db
from ..models import NetworthItem, NetworthValue
from ..preferences import build_calendar, get_preferences
from ..schemas import NetworthResponse, NetworthRow, NetworthValuePatch

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["networth"], dependencies=[Depends(require_auth)])
ZERO = Decimal("0")


def build_networth(db: Session, year: int, include_inactive: bool = False) -> NetworthResponse:
    prefs = get_preferences(db)
    months = build_calendar(year, prefs)

    stmt = select(NetworthItem).order_by(NetworthItem.sort_order, NetworthItem.id)
    if not include_inactive:
        stmt = stmt.where(NetworthItem.is_active.is_(True))
    items = list(db.execute(stmt).scalars().all())

    year_span = sorted({m["year"] for m in months})
    values = {
        (v.item_id, v.year, v.month): Decimal(v.amount)
        for v in db.execute(
            select(NetworthValue).where(NetworthValue.year.in_(year_span))
        ).scalars()
    }

    assets: list[NetworthRow] = []
    liabilities: list[NetworthRow] = []
    asset_totals = [ZERO] * 12
    liability_totals = [ZERO] * 12

    for item in items:
        cells: list[Optional[Decimal]] = []
        filled: list[Decimal] = []
        for column in months:
            amount = values.get((item.id, column["year"], column["month"]))
            cells.append(amount)
            if amount is not None:
                filled.append(amount)
                bucket = asset_totals if item.side == "asset" else liability_totals
                bucket[column["index"]] += amount
        row = NetworthRow(
            item_id=item.id,
            name=item.name,
            side=item.side,
            color=item.color,
            note=item.note,
            is_active=item.is_active,
            cells=cells,
            latest=filled[-1] if filled else ZERO,
            change=(filled[-1] - filled[0]) if len(filled) > 1 else ZERO,
        )
        (assets if item.side == "asset" else liabilities).append(row)

    # A month with no entries anywhere carries the previous month's balance
    # forward, so the net-worth line doesn't drop to zero on unfilled months.
    def carry(totals: list[Decimal]) -> list[Decimal]:
        out: list[Decimal] = []
        last = ZERO
        for index, total in enumerate(totals):
            has_data = any(row.cells[index] is not None for row in (assets + liabilities))
            value = total if has_data else last
            out.append(value)
            last = value
        return out

    net = [a - l for a, l in zip(carry(asset_totals), carry(liability_totals))]

    return NetworthResponse(
        year=year,
        months=months,
        assets=assets,
        liabilities=liabilities,
        asset_totals=asset_totals,
        liability_totals=liability_totals,
        net_worth=net,
    )


@router.get("/networth", response_model=NetworthResponse)
def read_networth(
    year: int = Query(..., ge=1900, le=2999),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    return build_networth(db, year, include_inactive)


@router.patch("/networth-values", status_code=status.HTTP_200_OK)
def patch_networth_value(patch: NetworthValuePatch, db: Session = Depends(get_db)):
    if db.get(NetworthItem, patch.item_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")

    existing = db.execute(
        select(NetworthValue).where(
            NetworthValue.item_id == patch.item_id,
            NetworthValue.year == patch.year,
            NetworthValue.month == patch.month,
        )
    ).scalar_one_or_none()

    if patch.amount is None:
        if existing is not None:
            db.delete(existing)
    elif existing is None:
        db.add(
            NetworthValue(
                item_id=patch.item_id,
                year=patch.year,
                month=patch.month,
                amount=patch.amount,
            )
        )
    else:
        existing.amount = patch.amount

    db.commit()
    log.info(
        "networth write item=%s %s-%s amount=%s",
        patch.item_id, patch.year, patch.month, patch.amount,
    )
    return {"ok": True}


@router.post("/networth-values/carry-forward", status_code=status.HTTP_200_OK)
def carry_forward(
    year: int = Query(..., ge=1900, le=2999),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    """Copy the previous month's balances into `month`. Most balances barely
    move month to month — this saves retyping all of them."""
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    previous = db.execute(
        select(NetworthValue).where(
            NetworthValue.year == prev_year, NetworthValue.month == prev_month
        )
    ).scalars().all()

    existing = {
        v.item_id: v
        for v in db.execute(
            select(NetworthValue).where(NetworthValue.year == year, NetworthValue.month == month)
        ).scalars()
    }

    for row in previous:
        if row.item_id in existing:
            existing[row.item_id].amount = row.amount
        else:
            db.add(
                NetworthValue(
                    item_id=row.item_id, year=year, month=month, amount=row.amount
                )
            )
    db.commit()
    log.info("networth carry-forward into %s-%s rows=%s", year, month, len(previous))
    return {"ok": True, "written": len(previous)}
