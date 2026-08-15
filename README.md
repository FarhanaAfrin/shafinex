# Shahfinex

A single-user personal finance tracker: a monthly category × month grid (like the
spreadsheet it replaces) with a dashboard, charts, net worth tracking and one-click
Excel export — and **everything in it is customizable at runtime**.

Vue 3 + Vuetify on the front, FastAPI + SQLAlchemy + Postgres behind, served as one
web service so there is a single URL, no CORS and one thing to keep awake.

---

## Run it locally

```bash
# 1. Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env          # set APP_PASSWORD and SECRET_KEY
.venv/bin/alembic upgrade head

# Seed the structure from your real workbook — categories, net-worth items and
# tools. Amounts stay empty; you type those into the app. Idempotent.
.venv/bin/python -m app.import_workbook "../Personal Finance Tracker - Stat with SHAH.xlsx" --year 2026
#   add --with-values to carry the workbook's numbers over as a starting point
# ...or start from a generic template instead:
.venv/bin/python -m app.seed default   # default | minimal | freelance | blank

# 2. Frontend
cd ../frontend
npm install
npm run build                 # or: npm run dev  (Vite on :5173, proxies /api)

# 3. Serve
cd ../backend
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 and sign in with `APP_PASSWORD`.

With no `DATABASE_URL` set it uses a local SQLite file (`backend/local.db`), so you
can try it before touching Neon. API docs live at `/api/docs`.

**Smoke test** (41 checks over auth, customization, cells, fiscal year, net worth,
aggregates, preferences and export):

```bash
cd backend && .venv/bin/pip install httpx && .venv/bin/python -m tests.test_smoke
```

## Deploy (Neon + Render, free tiers)

1. Create a Neon Postgres database, copy the connection string.
2. Push this repo to GitHub, then in Render: **New → Blueprint**, pick the repo
   (`render.yaml` is already here).
3. Set `DATABASE_URL` (Neon) and `APP_PASSWORD`. `SECRET_KEY` is generated for you.
4. First deploy runs `alembic upgrade head` automatically. Load starter categories
   from **Settings → Data → Starter templates**.

Render's free tier sleeps after ~15 minutes idle, so the first request after a
break takes 30–60 seconds. Neon scales to zero as well.

---

## What "fully customizable" means here

Nothing about the tracker's content is hardcoded — the seed data is a *starting
point*, not a fixture. From the UI you can change:

| Area | What you control |
|------|------------------|
| **Sheets** | Add, rename, recolour, reorder, hide or delete whole sheets. Each one is inflow or outflow, so custom sheets ("Side hustle", "Business costs") still aggregate correctly. |
| **Categories** | Add, rename, group, colour, reorder, note, hide or delete — per sheet, with drag-free up/down controls. |
| **Plan column** | Turn it off per sheet, or rename it ("Budget", "Expected", "Pipeline", "Target"). |
| **Net worth items** | Your own assets and liabilities; move an item between the two sides at any time. |
| **Tools** | The workbook's Tools tab: what you use, what it's for, the referral bonus, and a link or plain code you can copy. |
| **Money format** | Currency and symbol, symbol before/after, decimals, thousands separator, negative style (`-100` or `(100)`), compact big numbers, number locale. |
| **Calendar** | Which month the year starts in (fiscal years), month label style, landing page. |
| **Appearance** | Light/dark/system, accent colour, chart palette, row density, corner radius, text size, app name, your name, which sidebar sections exist. |
| **Goals** | Savings-rate target, monthly savings target, net-worth target, emergency-fund months — graded live on the dashboard. |
| **Data** | Starter templates (full / minimal / freelance / blank), copy last year's plan into a new year, clear a year, reset settings. |

Four starter templates ship with it; `default` is aimed at 25–40 year olds
(salary plus side income, rent or mortgage, subscriptions, student loans,
investment contributions, retirement accounts and crypto in net worth).

## Entering amounts

Seeding sets up the *structure* — sheets, categories, net-worth items, tools.
Every amount is entered in the app, into empty placeholder cells, exactly as you
filled the spreadsheet. Nothing is pre-populated behind your back.

The grid behaves like a spreadsheet, because that's what it replaces:

- **Arrow keys** move between cells, **Enter** goes down, **Shift+Enter** up, **Tab** right.
- Type `1.2k`, `2m`, `1,200`, `(450)` for negatives, or arithmetic like `900+50`.
- Every cell saves on its own, debounced, optimistically — a green border means
  saved, red means it didn't go through.
- Outflow sheets carry the workbook's **Balance row** (income − expenditure per
  month) pinned under the totals — green when you're up, red when you're down.
- Row menu: edit, fill across the year (for rent and subscriptions), clear, reorder, delete.
- Deleting always offers **hide** (keeps history) before **delete for good**.
- Net worth has **carry forward**, which copies last month's balances into this one.

## Architecture

```
backend/
  app/
    main.py           FastAPI app; also serves frontend/dist
    models.py         sheet, category, monthly_value, networth_item, networth_value, app_setting
    preferences.py    defaults + deep merge + the fiscal-calendar helper
    auth.py           single-user HMAC bearer tokens (stdlib only)
    seed.py           starter templates
    routers/          auth, structure, grid, networth, aggregates, preferences, export
  alembic/            migrations, from day one
  tests/test_smoke.py end-to-end check, no pytest needed
frontend/
  src/
    components/EditableGrid.vue   the grid (used by sheets and net worth)
    composables/useFormat.js      all money formatting and input parsing
    stores/                       session (auth + preferences + year), structure
    views/                        Login, Dashboard, Sheet, NetWorth, Charts, Export, Settings
```

**Data model.** Values are stored one cell per row — `(category, year, month, kind)`
— never as wide 12-month rows; wide rows exist only in API responses for the grid.
The plan/budget column is stored as `month = 0`, `kind = 'plan'`. A non-January
fiscal start only shifts which columns appear where: amounts stay attached to their
real calendar month, so nothing moves underneath you when you change the setting.

**Money.** `NUMERIC(16,2)` in the database, `Decimal` in Python, formatted per your
preferences on the way out.

**Auth.** One password in an env var, exchanged for an HMAC-signed token with an
expiry. No user table, no bank credentials, ever — manual entry only.

## Backup

Press **Export**. You get an .xlsx laid out like the original: a Dashboard tab, one
tab per sheet (with `Total` and `Balance` rows), Net Worth, Tools, and a snapshot of
your settings. Do it monthly; it is the whole backup strategy, and it means you are
never locked in.
