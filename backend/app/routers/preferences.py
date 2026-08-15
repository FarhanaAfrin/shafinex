"""Read/write the preference store, and reseed helpers."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth import require_auth
from ..db import get_db
from ..preferences import (
    DEFAULT_PREFERENCES,
    get_preferences,
    reset_preferences,
    save_preferences,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["preferences"], dependencies=[Depends(require_auth)])


@router.get("/preferences")
def read_preferences(db: Session = Depends(get_db)):
    return get_preferences(db)


@router.patch("/preferences")
def update_preferences(patch: dict, db: Session = Depends(get_db)):
    """Deep-merges, so the UI can send just the keys it changed."""
    prefs = save_preferences(db, patch)
    log.info("preferences updated keys=%s", list(patch.keys()))
    return prefs


@router.post("/preferences/reset")
def reset(db: Session = Depends(get_db)):
    log.warning("preferences reset to defaults")
    return reset_preferences(db)


@router.get("/preferences/defaults")
def defaults():
    return DEFAULT_PREFERENCES


@router.post("/structure/seed")
def seed_structure(
    replace: bool = Query(default=False, description="wipe existing structure first"),
    template: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    """Load a starter set of sheets/categories/net-worth items. Available from
    Settings so a user can start over without touching the server."""
    from ..seed import seed_database

    result = seed_database(db, replace=replace, template=template)
    log.info("structure seeded template=%s replace=%s result=%s", template, replace, result)
    return result


@router.get("/structure/templates")
def list_templates():
    from ..seed import TEMPLATES

    return [
        {"key": key, "name": value["name"], "description": value["description"]}
        for key, value in TEMPLATES.items()
    ]
