"""User preferences: defaults, merge, and the fiscal-calendar helper.

Every value here is editable from Settings in the UI. The backend reads the
same store so exports, aggregates and grids all follow the user's choices.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Setting

SETTINGS_KEY = "preferences"

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

DEFAULT_PREFERENCES: dict = {
    # Identity
    "app_name": "Shahfinex",
    "owner_name": "",
    # Money formatting
    "currency": "JPY",
    "currency_symbol": "¥",
    "symbol_position": "before",  # before | after
    "decimals": 0,
    "thousands_separator": True,
    "negative_style": "minus",  # minus | parentheses | red
    "compact_large_numbers": False,  # 1.2M instead of 1,200,000
    # Calendar
    "fiscal_start_month": 1,  # 1-12; grid columns roll forward from here
    "month_label_style": "short",  # short | long | numeric
    "week_start": 1,
    # Appearance
    "theme": "system",  # system | light | dark
    "accent": "#6366F1",
    "density": "comfortable",  # comfortable | compact
    "rounded": "lg",  # sm | md | lg | xl
    "font_scale": 1.0,
    "chart_palette": [
        "#6366F1", "#22C55E", "#F59E0B", "#EF4444", "#06B6D4",
        "#A855F7", "#EC4899", "#14B8A6", "#F97316", "#64748B",
    ],
    "show_cents_in_charts": False,
    # Behaviour
    "start_page": "dashboard",
    "autosave_delay_ms": 600,
    "confirm_before_delete": True,
    "highlight_over_budget": True,
    "carry_plan_forward": True,  # new year inherits last year's plan column
    # Goals — the numbers the dashboard grades you against
    "goals": {
        "savings_rate_target": 20,
        "monthly_savings_target": 0,
        "net_worth_target": 0,
        "emergency_fund_months": 6,
    },
    # Navigation: users can hide sections they don't use
    "visible_sections": [
        "dashboard", "sheets", "networth", "visualization", "tools", "export", "settings",
    ],
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def get_preferences(db: Session) -> dict:
    row = db.get(Setting, SETTINGS_KEY)
    stored = row.value if row else {}
    return _deep_merge(DEFAULT_PREFERENCES, stored)


def save_preferences(db: Session, patch: dict) -> dict:
    row = db.get(Setting, SETTINGS_KEY)
    merged = _deep_merge(row.value if row else {}, patch)
    if row is None:
        db.add(Setting(key=SETTINGS_KEY, value=merged))
    else:
        row.value = merged
        # JSON columns need an explicit flag when mutated in place.
        db.add(row)
    db.commit()
    return _deep_merge(DEFAULT_PREFERENCES, merged)


def reset_preferences(db: Session) -> dict:
    row = db.get(Setting, SETTINGS_KEY)
    if row is not None:
        db.delete(row)
        db.commit()
    return dict(DEFAULT_PREFERENCES)


def month_label(month: int, style: str) -> str:
    name = MONTH_NAMES[month - 1]
    if style == "long":
        return name
    if style == "numeric":
        return f"{month:02d}"
    return name[:3]


def build_calendar(year: int, prefs: dict) -> list[dict]:
    """The 12 grid columns for a given year, honouring fiscal_start_month.

    Values are always stored against their real calendar year/month; only the
    column order and labels shift.
    """
    start = int(prefs.get("fiscal_start_month", 1) or 1)
    start = min(max(start, 1), 12)
    style = prefs.get("month_label_style", "short")
    months = []
    for offset in range(12):
        raw = start + offset - 1
        month = raw % 12 + 1
        col_year = year + raw // 12
        label = month_label(month, style)
        if col_year != year:
            label = f"{label} '{str(col_year)[2:]}"
        months.append({"index": offset, "year": col_year, "month": month, "label": label})
    return months


def current_period(prefs: dict) -> dict:
    """Which grid year/column 'today' falls into."""
    today = date.today()
    start = int(prefs.get("fiscal_start_month", 1) or 1)
    fiscal_year = today.year if today.month >= start else today.year - 1
    return {"year": fiscal_year, "month": today.month, "calendar_year": today.year}
