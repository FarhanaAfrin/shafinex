# Personal Finance Tracker — Project Context

> Single source of truth for goals, stack, data model, and decisions.
> Use this as the context file for AI-assisted development (Claude Code) and onboarding.

## 1. Goal

A **single-user** personal finance tracker web app that replicates and improves on an
Excel-based workflow ("Personal Finance Tracker – Stat with SHAH" workbook). Optimized for:

- **Low cost** — free tiers only (Neon, Render)
- **Low maintenance** — minimal services, minimal dependencies
- **Easy troubleshooting** — clear logs, readable code
- **Portability** — one-click Excel/CSV export, never locked in

The UI follows an ML-platform-style layout: left sidebar navigation, content cards,
Material Design components (reference screenshot: sidebar sections + stepper + filter
chips + stats table).

## 2. Source Workbook (seed data)

Five sheets — the app mirrors this structure:

| Sheet        | Content                                                                 |
|--------------|-------------------------------------------------------------------------|
| Dashboard    | Three bar charts: income by month, expenses by month, net worth         |
| Income       | 19 income categories × (expected + 12 monthly actuals), `Total income` row |
| Expenditure  | 52 expense categories × (budgeted + 12 monthly actuals), `Total expenditure` row, `Balance` row (`=Income!C22-Expenditure!C55`) |
| Net Worth    | Assets (17 items) and Liabilities (11 items), totals, net worth = assets − liabilities |
| Tools        | Cards/apps/services: tool, purpose, referral bonus, referral link or code |

Money format throughout is `[$¥]#,##0` — yen, no decimals. That is the app's
default currency preference, not a hardcoded assumption.

**Key insight:** this is a *monthly aggregate model* (category × month grid),
NOT a transaction ledger. The app is a **grid editor**, not a transaction app.

Categories are **seeded** from the workbook (`python -m app.import_workbook`),
then fully editable — see §11. **Seeding brings across structure only; amounts
are always entered from the UI** into empty placeholder cells. `--with-values`
is an explicit opt-in for carrying the workbook's numbers over.

## 3. Stack

| Layer     | Choice                                             | Notes |
|-----------|----------------------------------------------------|-------|
| Frontend  | Vue 3 (Composition API) + Vite                     | |
| UI kit    | **Vuetify** (Material Design)                      | Matches target look with least custom CSS. `v-data-table` / plain table + `v-text-field` cells for the editable grid |
| Charts    | Plotly.js (direct, via `ref`)                      | |
| State     | Pinia (year selector, active sheet, auth token)    | |
| HTTP      | axios or fetch                                     | |
| Backend   | FastAPI + SQLAlchemy + Pydantic + Uvicorn          | |
| Migrations| Alembic — from day one                             | |
| Database  | Neon (serverless Postgres, free tier)              | Scales to zero |
| Hosting   | Render free tier — **single web service**          | FastAPI serves the built Vue `dist/` via `StaticFiles` → no CORS, one URL, one thing to sleep |
| Excel I/O | openpyxl (export), pandas/openpyxl (seed import)   | |

### Accepted trade-offs
- Two languages / SPA + API instead of the original one-file Streamlit idea —
  chosen deliberately for stack practice; maintenance cost acknowledged.
- Render free tier sleeps after ~15 min idle → ~30–60 s cold start; Neon also
  scales to zero, so cold starts can stack. Acceptable for personal use.

## 4. Data Model (normalized cells, not wide rows)

```sql
-- sheets are rows, not an enum, so users can add their own tabs
-- kind: 'inflow' | 'outflow'  (tells the aggregates which way money moves)
sheet(id PK, slug UNIQUE, name, kind, icon, color, plan_label, show_plan BOOL,
      sort_order, is_active BOOL DEFAULT true)

category(id PK, sheet_id FK ON DELETE CASCADE, name, group_name, color, note,
         sort_order, is_active BOOL DEFAULT true,
         UNIQUE(sheet_id, name))

-- kind: 'plan' | 'actual';  month 0 + kind 'plan' IS the budget/expected column
monthly_value(
  id PK, category_id FK ON DELETE CASCADE, year INT, month INT (0-12), kind,
  amount NUMERIC(16,2), created_at, updated_at,
  UNIQUE(category_id, year, month, kind)   -- upsert target
)

-- side: 'asset' | 'liability'
networth_item(id PK, side, name, color, note, sort_order, is_active,
              UNIQUE(side, name))

networth_value(
  id PK, item_id FK ON DELETE CASCADE, year INT, month INT, amount NUMERIC(16,2),
  created_at, updated_at,
  UNIQUE(item_id, year, month)
)

-- the workbook's Tools tab
tool(id PK, name UNIQUE, purpose, bonus, link, note, sort_order, is_active)

-- free-form JSON preference store: appearance, currency, calendar, goals
app_setting(key PK, value JSON, created_at, updated_at)
```

Decisions:
- **Year dimension** added (Excel has none) — topbar year selector; multi-year support built in.
- Amounts stored as `NUMERIC(16,2)`; currency is a *preference*, JPY by default.
- Categories are FK references, never free text.
- Wide 12-month rows exist **only** in API response shapes for the grid — never in the DB.
- Soft-disable via `is_active` is the default delete; hard delete is opt-in (`?hard=true`).
- **Fiscal start month** is a preference. It only shifts which columns appear where;
  values stay attached to their real calendar year/month, so changing it never
  moves data underneath the user.

## 5. API Contract (outline)

All routes are under `/api` and require the bearer token except `/api/auth/login`
and `/api/health`.

```
POST   /auth/login                     -> { token, expires_at }   # single user, env-var secret
GET    /meta                           -> preferences + current period + available years

GET    /sheets            POST /sheets            PATCH/DELETE /sheets/{id}   POST /sheets/reorder
GET    /categories        POST /categories        PATCH/DELETE /categories/{id}
                                                  POST /categories/reorder
GET    /networth-items    POST /networth-items    PATCH/DELETE /networth-items/{id}
                                                  POST /networth-items/reorder
GET    /tools             POST /tools             PATCH/DELETE /tools/{id}
                                                  POST /tools/reorder

GET    /grid?sheet=&year=              -> wide rows: category + plan + 12 months + total/avg/variance;
                                          outflow sheets also carry balance_row + balance_plan
PATCH  /values                         -> upsert one cell { category_id, year, month, kind, amount }
PATCH  /values/bulk                    -> all-or-nothing batch
POST   /values/fill-row                -> repeat one amount across the year
POST   /values/copy-year               -> start a year from last year's plan
DELETE /values/year                    -> clear a year (optionally one sheet)

GET    /networth?year=                 -> assets/liabilities grid + net worth series
PATCH  /networth-values                -> upsert one cell
POST   /networth-values/carry-forward  -> copy last month's balances into this one

GET    /aggregates?year=               -> monthly totals, balance, savings rate, category
                                          breakdown, plan-vs-actual, net worth, goal progress
GET    /preferences  PATCH /preferences  POST /preferences/reset
GET    /structure/templates             POST /structure/seed?template=&replace=
GET    /export?year=                   -> .xlsx: Dashboard, one tab per sheet (with Total +
                                          Balance rows), Net Worth, Tools, Settings
```

`DELETE` on a sheet/category/item soft-disables by default; `?hard=true` removes
it and its values.

- Save strategy: **debounced per-cell PATCH with optimistic UI** + subtle "saved"
  indicator. No whole-sheet POST (partial-failure mess).
- Import validation rule (if CSV import is added): reject file with row-level
  error report; never silent partial import.

## 6. UI Structure

Left sidebar sections (mirrors workbook tabs; the sheet entries are generated
from the `sheet` table, so custom sheets appear automatically):
1. **Dashboard** — cards: income, expenses, saved, net worth; goal progress; charts
2. **Income** — editable grid (categories × months, expected column)
3. **Expenditure** — editable grid (categories × months, budget column, variance
   column) with the workbook's sticky **Balance row** underneath the totals
   (green when positive, red when negative). Outflow sheets only.
4. **Net Worth** — assets/liabilities editable grids + net worth over time
5. **Charts** — Plotly: category pie/bar, monthly trend, plan-vs-actual,
   cumulative savings, savings rate by month
6. **Tools** — the workbook's Tools tab as cards: purpose, referral bonus, and a
   link button or a copyable code
7. **Export** — download full workbook (.xlsx) — doubles as the backup ritual
8. **Settings** — everything customizable (see §11)

Topbar: year selector + dark-mode toggle (Pinia state).

The grid is one component (`EditableGrid.vue`) used by both sheets and net worth:
spreadsheet keyboard nav, per-cell debounced optimistic save with saved/error
state, and input parsing for `1.2k`, `1,200`, `(450)`, `900+50`.

## 7. Security & Access

- Single user. `POST /api/auth/login` checks `APP_PASSWORD` (env var) and returns an
  **HMAC-signed token** with an expiry (`SECRET_KEY`, `TOKEN_TTL_DAYS`); a FastAPI
  dependency verifies it on every other route. Stdlib only, no user table.
- HTTPS provided by Render.
- Manual entry only — no bank credentials, ever.

## 8. Operational

- **Backup:** monthly ritual = press the Export button (full .xlsx download).
- **Logging:** Python `logging` to stdout (visible in Render dashboard);
  log every write with payload.
- **Migrations:** Alembic for every schema change.
- **Local dev:** same stack locally — `uvicorn` + `npm run dev` (Vite proxy to API),
  local Postgres or Neon dev branch.
- **Seeding:** `python -m app.import_workbook "<workbook>.xlsx" [--year Y] [--replace]
  [--with-values]` reads the original workbook (Income, Expenditure, Net Worth, Tools
  tabs), skips `Total…`/`Balance` rows, and imports **names only by default** —
  amounts are entered from the UI. Idempotent.
  The author's referral links are **imported from the user's own file, never shipped
  as seed data** — see §10.
  `python -m app.seed <default|minimal|freelance|blank>` loads a generic starter set
  instead; the same templates are available in-app under Settings → Data.
- **Testing:** `python -m tests.test_smoke` — end-to-end over auth, customization,
  cells, fiscal year, net worth, aggregates, preferences, export. No pytest needed.

## 9. Roadmap

**v1 (core) — built:**
- Auth, workbook-seeded categories, editable Income/Expenditure/Net Worth grids
- Dashboard totals + charts, budget-vs-actual, Excel export, year selector
- Full runtime customization (§11), goals, fiscal-year support

**v2 (later):**
- Optional transaction-level ledger feeding the monthly grid
- CSV import with validation report
- Drag-and-drop reordering (currently up/down controls)
- Recurring-cost templates; multi-currency conversion (display currency is
  already a preference, but there is no FX conversion)

## 11. Customization (design rule)

**Rule: seed data is a starting point, never a fixture.** Anything a user might
reasonably want to change is a row or a preference, not a constant in code. New
features must follow this — no hardcoded category names, currency symbols,
colours or month labels anywhere in the codebase.

Target user is 25–40, so the defaults assume salary + side income, rent or
mortgage, subscriptions, student loans, investment contributions, and net-worth
items including retirement accounts and crypto.

Editable from the UI (Settings, or in place on each grid):

| Area | Controls |
|------|----------|
| Sheets | add / rename / recolour / icon / reorder / hide / delete; inflow vs outflow; plan column on-off and its label |
| Categories | add / rename / group / colour / note / reorder / hide / delete; move between sheets (API) |
| Net worth | own asset & liability items; move an item between sides |
| Tools | add / edit / reorder / hide / delete; purpose, referral bonus, link **or** plain code |
| Money format | currency + symbol, symbol position, decimals, thousands separator, negative style, compact numbers, locale |
| Calendar | fiscal start month, month label style, landing page |
| Appearance | light/dark/system, accent, chart palette, density, corner radius, text size, app name, owner name, visible sidebar sections |
| Goals | savings-rate %, monthly savings, net-worth target, emergency-fund months — graded on the dashboard |
| Data | starter templates, copy last year's plan forward, clear a year, reset preferences |

Preferences live in `app_setting` as one JSON blob, merged over
`DEFAULT_PREFERENCES` in `app/preferences.py`. `PATCH /api/preferences` deep-merges,
so the UI sends only what changed. The backend reads the same store, so exports,
aggregates and grids all follow the user's choices.

## 10. Non-Goals

- Multi-user / roles
- Bank integrations
- Mobile app (responsive web is enough)
- Redistribution of the original Stat with SHAH workbook (copyrighted;
  personal recreation only)
