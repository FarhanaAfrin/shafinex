"""Expenses, the people you split them with, and who owes you what.

Accounting rule, in one line: **only your own share reaches the monthly grid.**
The rest of a split bill is a receivable until the person settles up. Money coming
back is not income — it never was an expense to you — so settling a share changes
no totals, it just clears the debt.

Every expense records what it posted (`applied_*`), so editing or deleting one
reverses exactly what it added rather than guessing.
"""

from typing import Optional

import logging
from decimal import Decimal
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..auth import require_auth
from ..db import get_db
from ..models import Category, Expense, ExpenseShare, MonthlyValue, Person
from ..schemas import (
    ExpenseCreate,
    ExpenseOut,
    ExpenseUpdate,
    PersonBalance,
    PersonCreate,
    PersonOut,
    PersonUpdate,
    ReorderRequest,
    ShareOut,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["expenses"], dependencies=[Depends(require_auth)])
ZERO = Decimal("0")


# ------------------------------------------------------------------ grid posting
def _adjust_cell(db: Session, category_id: int, year: int, month: int, delta: Decimal) -> None:
    """Add `delta` to one monthly cell, creating or removing the row as needed."""
    if delta == ZERO:
        return
    row = db.execute(
        select(MonthlyValue).where(
            MonthlyValue.category_id == category_id,
            MonthlyValue.year == year,
            MonthlyValue.month == month,
            MonthlyValue.kind == "actual",
        )
    ).scalar_one_or_none()

    if row is None:
        if delta != ZERO:
            db.add(
                MonthlyValue(
                    category_id=category_id, year=year, month=month, kind="actual", amount=delta
                )
            )
        return

    total = Decimal(row.amount) + delta
    if total == ZERO:
        db.delete(row)
    else:
        row.amount = total


def _unpost(db: Session, expense: Expense) -> None:
    """Reverse whatever this expense previously contributed."""
    if expense.applied_amount is None:
        return
    _adjust_cell(
        db,
        expense.applied_category_id,
        expense.applied_year,
        expense.applied_month,
        -Decimal(expense.applied_amount),
    )
    expense.applied_amount = None
    expense.applied_category_id = None
    expense.applied_year = None
    expense.applied_month = None


def _post(db: Session, expense: Expense) -> None:
    """Post the current share into the current category and month."""
    share = Decimal(expense.my_share)
    _adjust_cell(db, expense.category_id, expense.spent_on.year, expense.spent_on.month, share)
    expense.applied_amount = share
    expense.applied_category_id = expense.category_id
    expense.applied_year = expense.spent_on.year
    expense.applied_month = expense.spent_on.month


def _compute_my_share(total: Decimal, shares: list) -> Decimal:
    owed = sum((Decimal(s.amount) for s in shares), ZERO)
    if owed > total:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Other people's shares ({owed}) exceed the total ({total})",
        )
    return total - owed


def _serialize(expense: Expense) -> ExpenseOut:
    return ExpenseOut(
        id=expense.id,
        spent_on=expense.spent_on,
        merchant=expense.merchant,
        note=expense.note,
        category_id=expense.category_id,
        category_name=expense.category.name if expense.category else "",
        total_amount=Decimal(expense.total_amount),
        my_share=Decimal(expense.my_share),
        is_split=expense.is_split,
        source=expense.source,
        shares=[
            ShareOut(
                id=s.id,
                person_id=s.person_id,
                person_name=s.person.name if s.person else "",
                amount=Decimal(s.amount),
                settled_at=s.settled_at,
            )
            for s in expense.shares
        ],
    )


def _load(db: Session, expense_id: int) -> Expense:
    expense = db.execute(
        select(Expense)
        .options(selectinload(Expense.shares).selectinload(ExpenseShare.person), selectinload(Expense.category))
        .where(Expense.id == expense_id)
    ).scalar_one_or_none()
    if expense is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
    return expense


# ------------------------------------------------------------------ people
@router.get("/people", response_model=list[PersonOut])
def list_people(include_inactive: bool = False, db: Session = Depends(get_db)):
    stmt = select(Person).order_by(Person.sort_order, Person.id)
    if not include_inactive:
        stmt = stmt.where(Person.is_active.is_(True))
    return db.execute(stmt).scalars().all()


@router.post("/people", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
def create_person(payload: PersonCreate, db: Session = Depends(get_db)):
    order = db.execute(select(func.coalesce(func.max(Person.sort_order), -1))).scalar_one() + 1
    person = Person(**payload.model_dump(), sort_order=order)
    person.name = person.name.strip()
    db.add(person)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Someone with that name already exists")
    log.info("person created id=%s name=%s", person.id, person.name)
    return person


@router.patch("/people/{person_id}", response_model=PersonOut)
def update_person(person_id: int, payload: PersonUpdate, db: Session = Depends(get_db)):
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(person, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Someone with that name already exists")
    return person


@router.delete("/people/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(person_id: int, hard: bool = False, db: Session = Depends(get_db)):
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")
    if hard:
        outstanding = db.execute(
            select(func.count())
            .select_from(ExpenseShare)
            .where(ExpenseShare.person_id == person_id, ExpenseShare.settled_at.is_(None))
        ).scalar_one()
        if outstanding:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{person.name} still owes you on {outstanding} expense(s) — settle or hide instead",
            )
        db.delete(person)
    else:
        person.is_active = False
    db.commit()


@router.post("/people/reorder", response_model=list[PersonOut])
def reorder_people(payload: ReorderRequest, db: Session = Depends(get_db)):
    for position, person_id in enumerate(payload.ids):
        person = db.get(Person, person_id)
        if person is not None:
            person.sort_order = position
    db.commit()
    return db.execute(select(Person).order_by(Person.sort_order, Person.id)).scalars().all()


@router.get("/people/balances", response_model=list[PersonBalance])
def people_balances(db: Session = Depends(get_db)):
    """What each person currently owes you, and what they have already paid back."""
    people = db.execute(select(Person).order_by(Person.sort_order, Person.id)).scalars().all()
    shares = db.execute(select(ExpenseShare)).scalars().all()

    owed: dict[int, Decimal] = {}
    settled: dict[int, Decimal] = {}
    counts: dict[int, int] = {}
    for share in shares:
        amount = Decimal(share.amount)
        if share.settled_at is None:
            owed[share.person_id] = owed.get(share.person_id, ZERO) + amount
            counts[share.person_id] = counts.get(share.person_id, 0) + 1
        else:
            settled[share.person_id] = settled.get(share.person_id, ZERO) + amount

    return [
        PersonBalance(
            person=PersonOut.model_validate(person),
            owed=owed.get(person.id, ZERO),
            settled=settled.get(person.id, ZERO),
            open_items=counts.get(person.id, 0),
        )
        for person in people
    ]


# ------------------------------------------------------------------ expenses
@router.get("/expenses", response_model=list[ExpenseOut])
def list_expenses(
    year: Optional[int] = Query(default=None),
    month: Optional[int] = Query(default=None, ge=1, le=12),
    person_id: Optional[int] = Query(default=None),
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Expense)
        .options(selectinload(Expense.shares).selectinload(ExpenseShare.person), selectinload(Expense.category))
        .order_by(Expense.spent_on.desc(), Expense.id.desc())
        .limit(limit)
    )
    if year:
        stmt = stmt.where(func.extract("year", Expense.spent_on) == year)
    if month:
        stmt = stmt.where(func.extract("month", Expense.spent_on) == month)
    if person_id:
        stmt = stmt.join(ExpenseShare).where(ExpenseShare.person_id == person_id)
    return [_serialize(e) for e in db.execute(stmt).scalars().unique().all()]


@router.post("/expenses", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db)):
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")

    shares = payload.shares if payload.is_split else []
    for share in shares:
        if db.get(Person, share.person_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Person {share.person_id} not found")

    expense = Expense(
        spent_on=payload.spent_on,
        merchant=payload.merchant,
        note=payload.note,
        category_id=payload.category_id,
        total_amount=payload.total_amount,
        my_share=_compute_my_share(payload.total_amount, shares),
        is_split=bool(shares),
        source=payload.source,
        extraction=payload.extraction,
    )
    for share in shares:
        expense.shares.append(ExpenseShare(person_id=share.person_id, amount=share.amount))

    db.add(expense)
    db.flush()
    _post(db, expense)
    db.commit()

    log.info(
        "expense created id=%s total=%s my_share=%s split=%s posted to %s-%s",
        expense.id, expense.total_amount, expense.my_share, expense.is_split,
        expense.applied_year, expense.applied_month,
    )
    return _serialize(_load(db, expense.id))


@router.patch("/expenses/{expense_id}", response_model=ExpenseOut)
def update_expense(expense_id: int, payload: ExpenseUpdate, db: Session = Depends(get_db)):
    expense = _load(db, expense_id)
    data = payload.model_dump(exclude_unset=True)

    if "category_id" in data and db.get(Category, data["category_id"]) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")

    # Reverse the old contribution before changing anything.
    _unpost(db, expense)

    for field in ("spent_on", "merchant", "note", "category_id", "total_amount"):
        if field in data:
            setattr(expense, field, data[field])

    if "shares" in data or "is_split" in data:
        is_split = data.get("is_split", expense.is_split)
        incoming = payload.shares if payload.shares is not None else []
        if not is_split:
            incoming = []
        expense.shares.clear()
        db.flush()
        for share in incoming:
            if db.get(Person, share.person_id) is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"Person {share.person_id} not found")
            expense.shares.append(ExpenseShare(person_id=share.person_id, amount=share.amount))
        expense.is_split = bool(incoming)

    expense.my_share = _compute_my_share(Decimal(expense.total_amount), expense.shares)
    db.flush()
    _post(db, expense)
    db.commit()
    log.info("expense updated id=%s my_share=%s", expense_id, expense.my_share)
    return _serialize(_load(db, expense_id))


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = _load(db, expense_id)
    _unpost(db, expense)
    db.delete(expense)
    db.commit()
    log.info("expense deleted id=%s", expense_id)


@router.post("/expenses/shares/{share_id}/settle", response_model=ExpenseOut)
def settle_share(share_id: int, settled: bool = True, db: Session = Depends(get_db)):
    """Mark a share paid back. This clears the debt and deliberately does not
    touch any total: the money returning was never your expense."""
    share = db.get(ExpenseShare, share_id)
    if share is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Share not found")
    share.settled_at = datetime.now(timezone.utc) if settled else None
    db.commit()
    log.info("share %s id=%s", "settled" if settled else "reopened", share_id)
    return _serialize(_load(db, share.expense_id))


@router.post("/people/{person_id}/settle-all", response_model=PersonBalance)
def settle_person(person_id: int, db: Session = Depends(get_db)):
    """They paid you back in full."""
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")
    now = datetime.now(timezone.utc)
    open_shares = db.execute(
        select(ExpenseShare).where(
            ExpenseShare.person_id == person_id, ExpenseShare.settled_at.is_(None)
        )
    ).scalars().all()
    total = ZERO
    for share in open_shares:
        share.settled_at = now
        total += Decimal(share.amount)
    db.commit()
    log.info("settled all for person=%s amount=%s items=%s", person_id, total, len(open_shares))

    settled_total = db.execute(
        select(func.coalesce(func.sum(ExpenseShare.amount), 0)).where(
            ExpenseShare.person_id == person_id, ExpenseShare.settled_at.is_not(None)
        )
    ).scalar_one()
    return PersonBalance(
        person=PersonOut.model_validate(person),
        owed=ZERO,
        settled=Decimal(settled_total),
        open_items=0,
    )
