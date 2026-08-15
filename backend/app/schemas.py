"""Pydantic request/response shapes."""

from decimal import Decimal
from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SheetKind = Literal["inflow", "outflow"]
ValueKind = Literal["plan", "actual"]
Side = Literal["asset", "liability"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- auth
class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str
    expires_at: int


# ---------------------------------------------------------------- sheets
class SheetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: SheetKind = "outflow"
    icon: str = "mdi-table"
    color: str = "#6366F1"
    plan_label: str = "Planned"
    show_plan: bool = True
    slug: Optional[str] = None


class SheetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    kind: Optional[SheetKind] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    plan_label: Optional[str] = None
    show_plan: Optional[bool] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class SheetOut(ORMModel):
    id: int
    slug: str
    name: str
    kind: SheetKind
    icon: str
    color: str
    plan_label: str
    show_plan: bool
    sort_order: int
    is_active: bool


# ---------------------------------------------------------------- categories
class CategoryCreate(BaseModel):
    sheet_id: int
    name: str = Field(min_length=1, max_length=120)
    group_name: Optional[str] = None
    color: Optional[str] = None
    note: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    group_name: Optional[str] = None
    color: Optional[str] = None
    note: Optional[str] = None
    is_active: Optional[bool] = None
    sheet_id: Optional[int] = None


class CategoryOut(ORMModel):
    id: int
    sheet_id: int
    name: str
    group_name: Optional[str]
    color: Optional[str]
    note: Optional[str]
    sort_order: int
    is_active: bool


class ReorderRequest(BaseModel):
    """Full ordered list of ids; index becomes sort_order."""

    ids: list[int]


# ---------------------------------------------------------------- grid
class MonthColumn(BaseModel):
    index: int
    year: int
    month: int
    label: str


class GridRow(BaseModel):
    category_id: int
    name: str
    group_name: Optional[str]
    color: Optional[str]
    note: Optional[str]
    is_active: bool
    plan: Optional[Decimal]
    cells: list[Optional[Decimal]]
    total: Decimal
    average: Decimal
    variance: Optional[Decimal]  # plan - actual total (outflow) / actual - plan (inflow)


class GridResponse(BaseModel):
    sheet: SheetOut
    year: int
    months: list[MonthColumn]
    rows: list[GridRow]
    column_totals: list[Decimal]
    plan_total: Decimal
    grand_total: Decimal
    # The workbook's Balance row (income - expenditure per month); outflow sheets only.
    balance_row: Optional[list[Decimal]] = None
    balance_plan: Optional[Decimal] = None


class ValuePatch(BaseModel):
    category_id: int
    year: int
    month: int = Field(ge=0, le=12)  # 0 == the plan column
    kind: ValueKind = "actual"
    amount: Optional[Decimal] = None  # null clears the cell

    @field_validator("amount")
    @classmethod
    def _guard_range(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and abs(v) >= Decimal("10000000000000"):
            raise ValueError("amount out of range")
        return v


class BulkValuePatch(BaseModel):
    patches: list[ValuePatch]


class RowFillRequest(BaseModel):
    category_id: int
    year: int
    amount: Optional[Decimal] = None
    from_month: int = Field(default=1, ge=1, le=12)


# ---------------------------------------------------------------- net worth
class NetworthItemCreate(BaseModel):
    side: Side
    name: str = Field(min_length=1, max_length=120)
    color: Optional[str] = None
    note: Optional[str] = None


class NetworthItemUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    side: Optional[Side] = None
    color: Optional[str] = None
    note: Optional[str] = None
    is_active: Optional[bool] = None


class NetworthItemOut(ORMModel):
    id: int
    side: Side
    name: str
    color: Optional[str]
    note: Optional[str]
    sort_order: int
    is_active: bool


class NetworthRow(BaseModel):
    item_id: int
    name: str
    side: Side
    color: Optional[str]
    note: Optional[str]
    is_active: bool
    cells: list[Optional[Decimal]]
    latest: Decimal
    change: Decimal


class NetworthResponse(BaseModel):
    year: int
    months: list[MonthColumn]
    assets: list[NetworthRow]
    liabilities: list[NetworthRow]
    asset_totals: list[Decimal]
    liability_totals: list[Decimal]
    net_worth: list[Decimal]


class NetworthValuePatch(BaseModel):
    item_id: int
    year: int
    month: int = Field(ge=1, le=12)
    amount: Optional[Decimal] = None


# ---------------------------------------------------------------- aggregates
class SheetSummary(BaseModel):
    sheet: SheetOut
    monthly: list[Decimal]
    plan_total: Decimal
    actual_total: Decimal
    by_category: list[dict]


class AggregatesResponse(BaseModel):
    year: int
    months: list[MonthColumn]
    inflow_monthly: list[Decimal]
    outflow_monthly: list[Decimal]
    balance_monthly: list[Decimal]
    cumulative_balance: list[Decimal]
    total_inflow: Decimal
    total_outflow: Decimal
    balance: Decimal
    savings_rate: float
    net_worth_series: list[Decimal]
    net_worth_latest: Decimal
    assets_latest: Decimal
    liabilities_latest: Decimal
    sheets: list[SheetSummary]
    goals: dict
    available_years: list[int]


# ---------------------------------------------------------------- tools
class ToolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    purpose: Optional[str] = None
    bonus: Optional[str] = None
    link: Optional[str] = None
    note: Optional[str] = None


class ToolUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    purpose: Optional[str] = None
    bonus: Optional[str] = None
    link: Optional[str] = None
    note: Optional[str] = None
    is_active: Optional[bool] = None


class ToolOut(ORMModel):
    id: int
    name: str
    purpose: Optional[str]
    bonus: Optional[str]
    link: Optional[str]
    note: Optional[str]
    sort_order: int
    is_active: bool


# ---------------------------------------------------------------- preferences
class PreferencesPatch(BaseModel):
    model_config = ConfigDict(extra="allow")
