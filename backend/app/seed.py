"""Starter structures.

These are *defaults, not fixtures* — every sheet, category and item created
here can be renamed, recoloured, reordered or deleted from the UI. Templates
are aimed at the 25-40 bracket: salary plus side income, rent or mortgage,
subscriptions, student loans, investing, and a net-worth sheet that includes
retirement accounts and crypto.
"""

import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import Category, MonthlyValue, NetworthItem, NetworthValue, Sheet

log = logging.getLogger(__name__)

_DEFAULT_SHEETS = [
    {
        "slug": "income",
        "name": "Income",
        "kind": "inflow",
        "icon": "mdi-trending-up",
        "color": "#22C55E",
        "plan_label": "Expected",
        "categories": [
            ("Salary (net)", "Employment"),
            ("Bonus", "Employment"),
            ("Overtime", "Employment"),
            ("Freelance / side work", "Side income"),
            ("Contract work", "Side income"),
            ("Content / creator income", "Side income"),
            ("Dividends", "Investments"),
            ("Interest", "Investments"),
            ("Capital gains realised", "Investments"),
            ("Rental income", "Investments"),
            ("Tax refund", "Other"),
            ("Cashback & rewards", "Other"),
            ("Gifts received", "Other"),
            ("Reimbursements", "Other"),
            ("Other income", "Other"),
        ],
    },
    {
        "slug": "expenditure",
        "name": "Expenditure",
        "kind": "outflow",
        "icon": "mdi-trending-down",
        "color": "#EF4444",
        "plan_label": "Budget",
        "categories": [
            ("Rent", "Housing"),
            ("Mortgage", "Housing"),
            ("Property tax", "Housing"),
            ("Home insurance", "Housing"),
            ("Maintenance & repairs", "Housing"),
            ("Furniture & home goods", "Housing"),
            ("Electricity", "Utilities"),
            ("Gas", "Utilities"),
            ("Water", "Utilities"),
            ("Internet", "Utilities"),
            ("Mobile phone", "Utilities"),
            ("Groceries", "Food"),
            ("Dining out", "Food"),
            ("Coffee & snacks", "Food"),
            ("Food delivery", "Food"),
            ("Public transport", "Transport"),
            ("Fuel", "Transport"),
            ("Car payment", "Transport"),
            ("Car insurance", "Transport"),
            ("Parking & tolls", "Transport"),
            ("Taxi & rideshare", "Transport"),
            ("Health insurance", "Health"),
            ("Doctor & dentist", "Health"),
            ("Medication", "Health"),
            ("Gym & fitness", "Health"),
            ("Therapy & wellbeing", "Health"),
            ("Streaming services", "Subscriptions"),
            ("Music & audio", "Subscriptions"),
            ("Software & cloud", "Subscriptions"),
            ("News & memberships", "Subscriptions"),
            ("Clothing", "Lifestyle"),
            ("Personal care", "Lifestyle"),
            ("Hobbies", "Lifestyle"),
            ("Events & nightlife", "Lifestyle"),
            ("Gifts given", "Lifestyle"),
            ("Travel & flights", "Travel"),
            ("Accommodation", "Travel"),
            ("Holiday spending", "Travel"),
            ("Student loan", "Debt"),
            ("Credit card repayment", "Debt"),
            ("Personal loan", "Debt"),
            ("Childcare", "Family"),
            ("School fees", "Family"),
            ("Kids activities", "Family"),
            ("Pet care", "Family"),
            ("Family support", "Family"),
            ("Courses & training", "Growth"),
            ("Books", "Growth"),
            ("Emergency fund transfer", "Saving & investing"),
            ("Investment contribution", "Saving & investing"),
            ("Retirement contribution", "Saving & investing"),
            ("Income tax", "Taxes & fees"),
            ("Bank fees", "Taxes & fees"),
            ("Charity & donations", "Other"),
            ("Miscellaneous", "Other"),
        ],
    },
]

_DEFAULT_NETWORTH = {
    "asset": [
        "Cash on hand",
        "Current account",
        "Savings account",
        "Emergency fund",
        "Brokerage account",
        "Index funds / ETFs",
        "Retirement account",
        "Employer pension",
        "Crypto",
        "Property (market value)",
        "Vehicle",
        "Receivables (money owed to me)",
        "Other assets",
    ],
    "liability": [
        "Credit card balance",
        "Student loan",
        "Car loan",
        "Mortgage outstanding",
        "Personal loan",
        "Buy-now-pay-later",
        "Tax owed",
        "Money owed to family",
        "Other liabilities",
    ],
}

_MINIMAL_SHEETS = [
    {
        "slug": "income",
        "name": "Income",
        "kind": "inflow",
        "icon": "mdi-trending-up",
        "color": "#22C55E",
        "plan_label": "Expected",
        "categories": [("Salary", None), ("Side income", None), ("Other income", None)],
    },
    {
        "slug": "expenditure",
        "name": "Expenditure",
        "kind": "outflow",
        "icon": "mdi-trending-down",
        "color": "#EF4444",
        "plan_label": "Budget",
        "categories": [
            ("Housing", None),
            ("Food", None),
            ("Transport", None),
            ("Bills & subscriptions", None),
            ("Fun", None),
            ("Saving & investing", None),
        ],
    },
]

_MINIMAL_NETWORTH = {
    "asset": ["Cash", "Investments", "Retirement"],
    "liability": ["Credit card", "Loans"],
}

_FREELANCE_SHEETS = [
    {
        "slug": "income",
        "name": "Client income",
        "kind": "inflow",
        "icon": "mdi-briefcase-outline",
        "color": "#22C55E",
        "plan_label": "Pipeline",
        "categories": [
            ("Retainer clients", "Recurring"),
            ("Project work", "Projects"),
            ("Consulting", "Projects"),
            ("Digital products", "Passive"),
            ("Affiliate & sponsorship", "Passive"),
            ("Royalties", "Passive"),
            ("Interest & dividends", "Investments"),
            ("Other income", "Other"),
        ],
    },
    {
        "slug": "business-costs",
        "name": "Business costs",
        "kind": "outflow",
        "icon": "mdi-domain",
        "color": "#F59E0B",
        "plan_label": "Budget",
        "categories": [
            ("Software & tools", "Operating"),
            ("Hosting & domains", "Operating"),
            ("Contractors", "Operating"),
            ("Equipment", "Operating"),
            ("Coworking", "Operating"),
            ("Marketing & ads", "Growth"),
            ("Accounting & legal", "Admin"),
            ("Business insurance", "Admin"),
            ("Income tax set-aside", "Tax"),
            ("Sales tax set-aside", "Tax"),
        ],
    },
    {
        "slug": "personal",
        "name": "Personal spending",
        "kind": "outflow",
        "icon": "mdi-home-outline",
        "color": "#EF4444",
        "plan_label": "Budget",
        "categories": [
            ("Rent / mortgage", "Housing"),
            ("Utilities", "Housing"),
            ("Groceries", "Food"),
            ("Dining out", "Food"),
            ("Transport", "Transport"),
            ("Health & insurance", "Health"),
            ("Subscriptions", "Lifestyle"),
            ("Travel", "Lifestyle"),
            ("Saving & investing", "Saving"),
        ],
    },
]

_FREELANCE_NETWORTH = {
    "asset": [
        "Business account",
        "Tax set-aside account",
        "Personal current account",
        "Emergency fund",
        "Brokerage",
        "Retirement account",
        "Unpaid invoices",
    ],
    "liability": ["Credit card", "Tax owed", "Business loan", "Student loan"],
}

TEMPLATES: dict[str, dict] = {
    "default": {
        "name": "Full tracker",
        "description": "Income + Expenditure with ~70 categories and a detailed net worth sheet.",
        "sheets": _DEFAULT_SHEETS,
        "networth": _DEFAULT_NETWORTH,
    },
    "minimal": {
        "name": "Minimal",
        "description": "Nine broad categories. Fast to fill in, easy to expand later.",
        "sheets": _MINIMAL_SHEETS,
        "networth": _MINIMAL_NETWORTH,
    },
    "freelance": {
        "name": "Freelance / side business",
        "description": "Separates client income and business costs from personal spending.",
        "sheets": _FREELANCE_SHEETS,
        "networth": _FREELANCE_NETWORTH,
    },
    "blank": {
        "name": "Blank",
        "description": "Two empty sheets. Build your own category list from scratch.",
        "sheets": [
            {
                "slug": "income",
                "name": "Income",
                "kind": "inflow",
                "icon": "mdi-trending-up",
                "color": "#22C55E",
                "plan_label": "Expected",
                "categories": [],
            },
            {
                "slug": "expenditure",
                "name": "Expenditure",
                "kind": "outflow",
                "icon": "mdi-trending-down",
                "color": "#EF4444",
                "plan_label": "Budget",
                "categories": [],
            },
        ],
        "networth": {"asset": [], "liability": []},
    },
}


def _wipe(db: Session) -> None:
    db.execute(delete(MonthlyValue))
    db.execute(delete(NetworthValue))
    db.execute(delete(Category))
    db.execute(delete(NetworthItem))
    db.execute(delete(Sheet))
    db.flush()


def seed_database(db: Session, replace: bool = False, template: str = "default") -> dict:
    """Idempotent unless `replace` is set: existing names are skipped, not duplicated."""
    spec = TEMPLATES.get(template)
    if spec is None:
        raise ValueError(f"Unknown template '{template}'")

    if replace:
        _wipe(db)

    created = {"sheets": 0, "categories": 0, "networth_items": 0}

    for sheet_index, sheet_spec in enumerate(spec["sheets"]):
        sheet = db.execute(
            select(Sheet).where(Sheet.slug == sheet_spec["slug"])
        ).scalar_one_or_none()
        if sheet is None:
            sheet = Sheet(
                slug=sheet_spec["slug"],
                name=sheet_spec["name"],
                kind=sheet_spec["kind"],
                icon=sheet_spec["icon"],
                color=sheet_spec["color"],
                plan_label=sheet_spec["plan_label"],
                sort_order=sheet_index,
            )
            db.add(sheet)
            db.flush()
            created["sheets"] += 1

        existing_names = {
            name
            for name in db.execute(
                select(Category.name).where(Category.sheet_id == sheet.id)
            ).scalars()
        }
        order = len(existing_names)
        for name, group in sheet_spec["categories"]:
            if name in existing_names:
                continue
            db.add(
                Category(sheet_id=sheet.id, name=name, group_name=group, sort_order=order)
            )
            order += 1
            created["categories"] += 1

    for side, names in spec["networth"].items():
        existing_names = {
            name
            for name in db.execute(
                select(NetworthItem.name).where(NetworthItem.side == side)
            ).scalars()
        }
        order = len(existing_names)
        for name in names:
            if name in existing_names:
                continue
            db.add(NetworthItem(side=side, name=name, sort_order=order))
            order += 1
            created["networth_items"] += 1

    db.commit()
    log.info("seed complete template=%s created=%s", template, created)
    return {"template": template, "created": created}


def main() -> None:
    """CLI: python -m app.seed [template] [--replace]"""
    import sys

    from .db import SessionLocal

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    template = args[0] if args else "default"
    replace = "--replace" in sys.argv

    with SessionLocal() as db:
        result = seed_database(db, replace=replace, template=template)
    print(f"Seeded '{result['template']}': {result['created']}")


if __name__ == "__main__":
    main()
