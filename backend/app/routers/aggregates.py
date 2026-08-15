"""Server-computed numbers for the dashboard and charts.

Kept on the server so the frontend never re-implements the maths and Plotly
just plots what it is given.
"""

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_auth
from ..db import get_db
from ..models import Category, MonthlyValue, NetworthValue, Sheet
from ..preferences import build_calendar, current_period, get_preferences
from ..schemas import AggregatesResponse, SheetOut, SheetSummary
from .networth import build_networth

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["aggregates"], dependencies=[Depends(require_auth)])
ZERO = Decimal("0")


def available_years(db: Session) -> list[int]:
    years = set(db.execute(select(MonthlyValue.year).distinct()).scalars().all())
    years |= set(db.execute(select(NetworthValue.year).distinct()).scalars().all())
    years.add(current_period(get_preferences(db))["year"])
    return sorted(years)


@router.get("/aggregates", response_model=AggregatesResponse)
def read_aggregates(
    year: int = Query(..., ge=1900, le=2999),
    db: Session = Depends(get_db),
):
    prefs = get_preferences(db)
    months = build_calendar(year, prefs)
    year_span = sorted({m["year"] for m in months} | {year})

    sheets = list(
        db.execute(
            select(Sheet).where(Sheet.is_active.is_(True)).order_by(Sheet.sort_order, Sheet.id)
        ).scalars()
    )
    categories = list(
        db.execute(select(Category).where(Category.is_active.is_(True))).scalars()
    )
    by_id = {c.id: c for c in categories}

    values = list(
        db.execute(
            select(MonthlyValue).where(MonthlyValue.year.in_(year_span))
        ).scalars()
    )

    column_of = {(m["year"], m["month"]): m["index"] for m in months}

    inflow_monthly = [ZERO] * 12
    outflow_monthly = [ZERO] * 12
    summaries: list[SheetSummary] = []

    for sheet in sheets:
        sheet_categories = [c for c in categories if c.sheet_id == sheet.id]
        ids = {c.id for c in sheet_categories}
        monthly = [ZERO] * 12
        plan_total = ZERO
        per_category: dict[int, Decimal] = {c.id: ZERO for c in sheet_categories}

        for value in values:
            if value.category_id not in ids:
                continue
            amount = Decimal(value.amount)
            if value.kind == "plan":
                if value.year == year:
                    plan_total += amount
                continue
            index = column_of.get((value.year, value.month))
            if index is None:
                continue
            monthly[index] += amount
            per_category[value.category_id] += amount

        target = inflow_monthly if sheet.kind == "inflow" else outflow_monthly
        for index in range(12):
            target[index] += monthly[index]

        breakdown = sorted(
            (
                {
                    "category_id": cid,
                    "name": by_id[cid].name,
                    "color": by_id[cid].color,
                    "total": total,
                    "plan": next(
                        (
                            Decimal(v.amount)
                            for v in values
                            if v.category_id == cid and v.kind == "plan" and v.year == year
                        ),
                        None,
                    ),
                }
                for cid, total in per_category.items()
            ),
            key=lambda row: row["total"],
            reverse=True,
        )

        summaries.append(
            SheetSummary(
                sheet=SheetOut.model_validate(sheet),
                monthly=monthly,
                plan_total=plan_total,
                actual_total=sum(monthly, ZERO),
                by_category=breakdown,
            )
        )

    balance_monthly = [i - o for i, o in zip(inflow_monthly, outflow_monthly)]
    cumulative: list[Decimal] = []
    running = ZERO
    for value in balance_monthly:
        running += value
        cumulative.append(running)

    total_inflow = sum(inflow_monthly, ZERO)
    total_outflow = sum(outflow_monthly, ZERO)
    balance = total_inflow - total_outflow
    savings_rate = float(balance / total_inflow * 100) if total_inflow else 0.0

    networth = build_networth(db, year)
    assets_latest = next(
        (t for t in reversed(networth.asset_totals) if t != ZERO), ZERO
    )
    liabilities_latest = next(
        (t for t in reversed(networth.liability_totals) if t != ZERO), ZERO
    )

    goals = dict(prefs.get("goals", {}))
    goals["savings_rate_actual"] = round(savings_rate, 1)
    goals["monthly_savings_actual"] = float(
        balance / max(sum(1 for m in balance_monthly if m != ZERO), 1)
    )
    goals["net_worth_actual"] = float(networth.net_worth[-1] if networth.net_worth else ZERO)
    monthly_spend = total_outflow / max(sum(1 for m in outflow_monthly if m != ZERO), 1)
    goals["emergency_fund_months_actual"] = (
        round(float(assets_latest / monthly_spend), 1) if monthly_spend else 0.0
    )

    return AggregatesResponse(
        year=year,
        months=months,
        inflow_monthly=inflow_monthly,
        outflow_monthly=outflow_monthly,
        balance_monthly=balance_monthly,
        cumulative_balance=cumulative,
        total_inflow=total_inflow,
        total_outflow=total_outflow,
        balance=balance,
        savings_rate=round(savings_rate, 2),
        net_worth_series=networth.net_worth,
        net_worth_latest=networth.net_worth[-1] if networth.net_worth else ZERO,
        assets_latest=assets_latest,
        liabilities_latest=liabilities_latest,
        sheets=summaries,
        goals=goals,
        available_years=available_years(db),
    )


@router.get("/meta")
def read_meta(db: Session = Depends(get_db)):
    """Bootstrap payload the SPA fetches once on load."""
    prefs = get_preferences(db)
    return {
        "preferences": prefs,
        "current": current_period(prefs),
        "available_years": available_years(db),
    }
