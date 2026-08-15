"""CRUD for the things that make the app customizable: sheets, categories,
net-worth items. Everything here is user-editable at runtime."""

from typing import Optional

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import require_auth
from ..db import get_db
from ..models import Category, NetworthItem, Sheet, Tool
from ..schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    NetworthItemCreate,
    NetworthItemOut,
    NetworthItemUpdate,
    ReorderRequest,
    SheetCreate,
    SheetOut,
    SheetUpdate,
    ToolCreate,
    ToolOut,
    ToolUpdate,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["structure"], dependencies=[Depends(require_auth)])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "sheet"


def _next_order(db: Session, model, **filters) -> int:
    stmt = select(func.coalesce(func.max(model.sort_order), -1))
    for field, value in filters.items():
        stmt = stmt.where(getattr(model, field) == value)
    return db.execute(stmt).scalar_one() + 1


# ------------------------------------------------------------------ sheets
@router.get("/sheets", response_model=list[SheetOut])
def list_sheets(include_inactive: bool = False, db: Session = Depends(get_db)):
    stmt = select(Sheet).order_by(Sheet.sort_order, Sheet.id)
    if not include_inactive:
        stmt = stmt.where(Sheet.is_active.is_(True))
    return db.execute(stmt).scalars().all()


@router.post("/sheets", response_model=SheetOut, status_code=status.HTTP_201_CREATED)
def create_sheet(payload: SheetCreate, db: Session = Depends(get_db)):
    slug = base_slug = _slugify(payload.slug or payload.name)
    suffix = 2
    while db.execute(select(Sheet).where(Sheet.slug == slug)).scalar_one_or_none():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    sheet = Sheet(
        slug=slug,
        name=payload.name.strip(),
        kind=payload.kind,
        icon=payload.icon,
        color=payload.color,
        plan_label=payload.plan_label,
        show_plan=payload.show_plan,
        sort_order=_next_order(db, Sheet),
    )
    db.add(sheet)
    db.commit()
    log.info("sheet created id=%s slug=%s kind=%s", sheet.id, sheet.slug, sheet.kind)
    return sheet


@router.patch("/sheets/{sheet_id}", response_model=SheetOut)
def update_sheet(sheet_id: int, payload: SheetUpdate, db: Session = Depends(get_db)):
    sheet = db.get(Sheet, sheet_id)
    if sheet is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sheet not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(sheet, field, value)
    db.commit()
    log.info("sheet updated id=%s payload=%s", sheet_id, payload.model_dump(exclude_unset=True))
    return sheet


@router.delete("/sheets/{sheet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sheet(sheet_id: int, hard: bool = False, db: Session = Depends(get_db)):
    """Default is a soft disable (data kept). `?hard=true` removes the sheet and
    every value under it."""
    sheet = db.get(Sheet, sheet_id)
    if sheet is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sheet not found")
    if hard:
        db.delete(sheet)
    else:
        sheet.is_active = False
    db.commit()
    log.info("sheet %s id=%s", "deleted" if hard else "disabled", sheet_id)


@router.post("/sheets/reorder", response_model=list[SheetOut])
def reorder_sheets(payload: ReorderRequest, db: Session = Depends(get_db)):
    for position, sheet_id in enumerate(payload.ids):
        sheet = db.get(Sheet, sheet_id)
        if sheet is not None:
            sheet.sort_order = position
    db.commit()
    return db.execute(select(Sheet).order_by(Sheet.sort_order, Sheet.id)).scalars().all()


# ------------------------------------------------------------------ categories
@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    sheet: Optional[str] = Query(default=None, description="sheet slug"),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    stmt = select(Category).order_by(Category.sort_order, Category.id)
    if sheet:
        stmt = stmt.join(Sheet).where(Sheet.slug == sheet)
    if not include_inactive:
        stmt = stmt.where(Category.is_active.is_(True))
    return db.execute(stmt).scalars().all()


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    if db.get(Sheet, payload.sheet_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sheet not found")
    category = Category(
        sheet_id=payload.sheet_id,
        name=payload.name.strip(),
        group_name=payload.group_name,
        color=payload.color,
        note=payload.note,
        sort_order=_next_order(db, Category, sheet_id=payload.sheet_id),
    )
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A category with that name already exists")
    log.info("category created id=%s name=%s", category.id, category.name)
    return category


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    data = payload.model_dump(exclude_unset=True)
    if "sheet_id" in data and db.get(Sheet, data["sheet_id"]) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Target sheet not found")
    for field, value in data.items():
        setattr(category, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A category with that name already exists")
    log.info("category updated id=%s payload=%s", category_id, data)
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, hard: bool = False, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    if hard:
        db.delete(category)
    else:
        category.is_active = False
    db.commit()
    log.info("category %s id=%s", "deleted" if hard else "disabled", category_id)


@router.post("/categories/reorder", response_model=list[CategoryOut])
def reorder_categories(payload: ReorderRequest, db: Session = Depends(get_db)):
    for position, category_id in enumerate(payload.ids):
        category = db.get(Category, category_id)
        if category is not None:
            category.sort_order = position
    db.commit()
    return (
        db.execute(
            select(Category)
            .where(Category.id.in_(payload.ids))
            .order_by(Category.sort_order, Category.id)
        )
        .scalars()
        .all()
    )


# ------------------------------------------------------------------ net worth items
@router.get("/networth-items", response_model=list[NetworthItemOut])
def list_networth_items(include_inactive: bool = False, db: Session = Depends(get_db)):
    stmt = select(NetworthItem).order_by(NetworthItem.side, NetworthItem.sort_order, NetworthItem.id)
    if not include_inactive:
        stmt = stmt.where(NetworthItem.is_active.is_(True))
    return db.execute(stmt).scalars().all()


@router.post(
    "/networth-items", response_model=NetworthItemOut, status_code=status.HTTP_201_CREATED
)
def create_networth_item(payload: NetworthItemCreate, db: Session = Depends(get_db)):
    item = NetworthItem(
        side=payload.side,
        name=payload.name.strip(),
        color=payload.color,
        note=payload.note,
        sort_order=_next_order(db, NetworthItem, side=payload.side),
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An item with that name already exists")
    log.info("networth item created id=%s name=%s", item.id, item.name)
    return item


@router.patch("/networth-items/{item_id}", response_model=NetworthItemOut)
def update_networth_item(
    item_id: int, payload: NetworthItemUpdate, db: Session = Depends(get_db)
):
    item = db.get(NetworthItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An item with that name already exists")
    return item


@router.delete("/networth-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_networth_item(item_id: int, hard: bool = False, db: Session = Depends(get_db)):
    item = db.get(NetworthItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    if hard:
        db.delete(item)
    else:
        item.is_active = False
    db.commit()


@router.post("/networth-items/reorder", response_model=list[NetworthItemOut])
def reorder_networth_items(payload: ReorderRequest, db: Session = Depends(get_db)):
    for position, item_id in enumerate(payload.ids):
        item = db.get(NetworthItem, item_id)
        if item is not None:
            item.sort_order = position
    db.commit()
    return (
        db.execute(select(NetworthItem).order_by(NetworthItem.side, NetworthItem.sort_order))
        .scalars()
        .all()
    )


# ------------------------------------------------------------------ tools
@router.get("/tools", response_model=list[ToolOut])
def list_tools(include_inactive: bool = False, db: Session = Depends(get_db)):
    stmt = select(Tool).order_by(Tool.sort_order, Tool.id)
    if not include_inactive:
        stmt = stmt.where(Tool.is_active.is_(True))
    return db.execute(stmt).scalars().all()


@router.post("/tools", response_model=ToolOut, status_code=status.HTTP_201_CREATED)
def create_tool(payload: ToolCreate, db: Session = Depends(get_db)):
    tool = Tool(
        name=payload.name.strip(),
        purpose=payload.purpose,
        bonus=payload.bonus,
        link=payload.link,
        note=payload.note,
        sort_order=_next_order(db, Tool),
    )
    db.add(tool)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A tool with that name already exists")
    log.info("tool created id=%s name=%s", tool.id, tool.name)
    return tool


@router.patch("/tools/{tool_id}", response_model=ToolOut)
def update_tool(tool_id: int, payload: ToolUpdate, db: Session = Depends(get_db)):
    tool = db.get(Tool, tool_id)
    if tool is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tool not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tool, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A tool with that name already exists")
    return tool


@router.delete("/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tool(tool_id: int, hard: bool = False, db: Session = Depends(get_db)):
    tool = db.get(Tool, tool_id)
    if tool is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tool not found")
    if hard:
        db.delete(tool)
    else:
        tool.is_active = False
    db.commit()


@router.post("/tools/reorder", response_model=list[ToolOut])
def reorder_tools(payload: ReorderRequest, db: Session = Depends(get_db)):
    for position, tool_id in enumerate(payload.ids):
        tool = db.get(Tool, tool_id)
        if tool is not None:
            tool.sort_order = position
    db.commit()
    return db.execute(select(Tool).order_by(Tool.sort_order, Tool.id)).scalars().all()
