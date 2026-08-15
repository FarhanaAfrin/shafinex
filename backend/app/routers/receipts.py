"""Receipt scanning endpoint. Accepts an image and nothing else."""

import logging
from decimal import Decimal, InvalidOperation
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_auth
from ..config import get_settings
from ..db import get_db
from ..models import Category, Sheet
from ..schemas import ReceiptDraft
from ..services.receipts import (
    ALLOWED_MEDIA_TYPES,
    MAX_IMAGE_BYTES,
    ReceiptError,
    extract_receipt,
    sniff_media_type,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["receipts"], dependencies=[Depends(require_auth)])


def _decimal(value) -> "Decimal | None":
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


@router.get("/receipts/status")
def receipts_status():
    """The UI hides the scan button when this is off."""
    settings = get_settings()
    return {
        "enabled": settings.receipts_enabled,
        "model": settings.receipt_model if settings.receipts_enabled else None,
        "accepted_types": sorted(ALLOWED_MEDIA_TYPES),
        "max_bytes": MAX_IMAGE_BYTES,
    }


@router.post("/receipts/scan", response_model=ReceiptDraft)
async def scan_receipt(image: UploadFile = File(...), db: Session = Depends(get_db)):
    """Read a receipt photo into a draft. Saves nothing — the user confirms first."""
    if not get_settings().receipts_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Receipt scanning is off — set ANTHROPIC_API_KEY to enable it",
        )

    data = await image.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That file was empty")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Images must be under {MAX_IMAGE_BYTES // (1024 * 1024)} MB",
        )

    # Images only — decided by content, not by the declared Content-Type.
    media_type = sniff_media_type(data)
    if media_type is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Only images are accepted here (JPEG, PNG, WebP or GIF)",
        )

    # Offer the model the user's own outflow categories to choose from.
    categories = list(
        db.execute(
            select(Category)
            .join(Sheet)
            .where(
                Category.is_active.is_(True),
                Sheet.is_active.is_(True),
                Sheet.kind == "outflow",
            )
            .order_by(Category.sort_order)
        ).scalars()
    )
    by_name = {c.name.strip().lower(): c for c in categories}

    try:
        draft = extract_receipt(data, media_type, [c.name for c in categories])
    except ReceiptError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error))

    warnings: list[str] = []
    if not draft.is_receipt:
        warnings.append("This does not look like a receipt — check the details before saving.")
    if draft.confidence < 0.6:
        warnings.append("The image was hard to read. Please check every figure.")

    # Map the suggested name back to a real category; never invent one.
    suggested = by_name.get((draft.suggested_category or "").strip().lower())
    if draft.suggested_category and suggested is None:
        warnings.append(f"Suggested category “{draft.suggested_category}” isn’t one of yours.")

    total = _decimal(draft.total)
    if total is None:
        warnings.append("No total was readable — enter it by hand.")
    elif total <= 0:
        warnings.append("The total read as zero or negative — check it.")
        total = None

    spent_on = None
    if draft.spent_on:
        try:
            spent_on = date.fromisoformat(draft.spent_on)
        except ValueError:
            warnings.append(f"Could not read the date “{draft.spent_on}”.")
    if spent_on is None:
        spent_on = date.today()
        warnings.append("No date found — using today.")
    elif spent_on > date.today():
        warnings.append("The date is in the future — check it.")

    return ReceiptDraft(
        is_receipt=draft.is_receipt,
        merchant=(draft.merchant or "").strip() or None,
        spent_on=spent_on,
        currency=draft.currency,
        total=total,
        subtotal=_decimal(draft.subtotal),
        tax=_decimal(draft.tax),
        tip=_decimal(draft.tip),
        payment_method=draft.payment_method,
        line_items=[{"description": i.description, "amount": _decimal(i.amount)} for i in draft.line_items],
        suggested_category_id=suggested.id if suggested else None,
        suggested_category_name=suggested.name if suggested else None,
        likely_shared=draft.likely_shared,
        likely_people_count=draft.likely_people_count,
        confidence=draft.confidence,
        notes=draft.notes,
        warnings=warnings,
    )
