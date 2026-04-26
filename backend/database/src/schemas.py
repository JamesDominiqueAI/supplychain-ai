from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


MovementType = Literal["sale", "purchase", "adjustment"]
JobStatus = Literal["pending", "running", "completed", "failed"]
OrderStatus = Literal[
    "draft",
    "approved",
    "placed",
    "in_transit",
    "partially_received",
    "arrived",
    "canceled",
    "delayed",
]


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class Business(BaseModel):
    business_id: str = Field(default_factory=new_id)
    name: str
    country: str = "Haiti"
    currency: str = "HTG"
    available_cash: float = 250000.0
    ai_enabled: bool = True
    ai_automation_enabled: bool = False
    notification_email: str | None = None
    critical_alerts_enabled: bool = True
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("notification_email")
    def validate_notification_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Notification email must be a valid email address")
        return normalized

    @field_validator("created_at", mode="after")
    def normalize_created_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class Product(BaseModel):
    product_id: str = Field(default_factory=new_id)
    business_id: str
    sku: str
    name: str
    category: str
    unit: str = "unit"
    reorder_point: int = 10
    target_days_of_cover: int = 14
    lead_time_days: int = 7
    current_stock: int = 0
    avg_daily_demand: float = 1.0
    unit_cost: float = 100.0
    preferred_supplier_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("sku")
    def normalize_sku(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("SKU is required")
        return normalized

    @field_validator("name", "category", "unit")
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be empty")
        return stripped

    @field_validator("created_at", mode="after")
    def normalize_created_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class Supplier(BaseModel):
    supplier_id: str = Field(default_factory=new_id)
    business_id: str
    name: str
    contact_phone: str | None = None
    lead_time_days: int = 7
    reliability_score: float = 0.8
    notes: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("name")
    def validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 2:
            raise ValueError("Supplier name must be at least 2 characters")
        return stripped

    @field_validator("created_at", mode="after")
    def normalize_created_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class InventoryMovement(BaseModel):
    movement_id: str = Field(default_factory=new_id)
    business_id: str
    product_id: str
    movement_type: MovementType
    quantity: int = Field(gt=0)
    occurred_at: datetime = Field(default_factory=utc_now)
    note: str | None = None

    @field_validator("occurred_at", mode="after")
    def normalize_occurred_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class PurchaseRecommendation(BaseModel):
    product_id: str
    sku: str
    product_name: str
    current_stock: int
    reorder_point: int
    predicted_7d_demand: float
    predicted_30d_demand: float
    days_of_cover: float
    eoq_order_qty: int
    recommended_order_qty: int
    estimated_cost: float
    urgency: Literal["low", "medium", "high", "critical"]
    recommendation_type: Literal["buy_now", "wait", "split_order"]
    confidence: Literal["medium", "high"]
    rationale: str


class ReplenishmentReport(BaseModel):
    report_id: str = Field(default_factory=new_id)
    business_id: str
    summary: str
    total_recommended_spend: float
    affordable_now: bool
    actions: list[str]
    recommendations: list[PurchaseRecommendation]
    generated_at: datetime = Field(default_factory=utc_now)

    @field_validator("generated_at", mode="after")
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class PurchaseOrder(BaseModel):
    order_id: str = Field(default_factory=new_id)
    business_id: str
    product_id: str
    sku: str
    product_name: str
    quantity: int = Field(gt=0)
    estimated_cost: float = Field(ge=0)
    status: OrderStatus = "placed"
    supplier_id: str | None = None
    supplier_name: str | None = None
    expected_delivery_date: datetime | None = None
    received_quantity: int = Field(default=0, ge=0)
    last_received_at: datetime | None = None
    is_late: bool = False
    days_late: int = Field(default=0, ge=0)
    source_report_id: str | None = None
    placed_by_type: Literal["user", "llm", "system"] = "user"
    placed_by_label: str | None = None
    note: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("expected_delivery_date", "last_received_at", mode="after")
    def normalize_optional_datetimes(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return ensure_utc(value)

    @field_validator("created_at", "updated_at", mode="after")
    def normalize_order_datetimes(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class AnalysisJob(BaseModel):
    job_id: str = Field(default_factory=new_id)
    business_id: str
    job_type: str
    status: JobStatus = "pending"
    result_report_id: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None

    @field_validator("created_at", mode="after")
    def normalize_created_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @field_validator("completed_at", mode="after")
    def normalize_completed_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return ensure_utc(value)


class InventoryHealthItem(BaseModel):
    product_id: str
    sku: str
    product_name: str
    current_stock: int
    reorder_point: int
    days_of_cover: float
    lead_time_days: int
    risk_level: Literal["healthy", "watch", "high", "critical"]


class CreateProductRequest(BaseModel):
    sku: str
    name: str
    category: str
    unit: str = "unit"
    reorder_point: int = Field(default=10, ge=0)
    target_days_of_cover: int = Field(default=14, ge=1)
    lead_time_days: int = Field(default=7, ge=1)
    current_stock: int = Field(default=0, ge=0)
    avg_daily_demand: float = Field(default=1.0, ge=0)
    unit_cost: float = Field(default=100.0, ge=0)
    preferred_supplier_id: str | None = None


class CreateSupplierRequest(BaseModel):
    name: str
    contact_phone: str | None = None
    lead_time_days: int = Field(default=7, ge=1)
    reliability_score: float = Field(default=0.8, ge=0, le=1)
    notes: str | None = None


class CreateInventoryMovementRequest(BaseModel):
    product_id: str
    movement_type: MovementType
    quantity: int = Field(gt=0)
    note: str | None = None


class CreatePurchaseOrderRequest(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)
    supplier_id: str | None = None
    estimated_cost: float | None = Field(default=None, ge=0)
    expected_delivery_date: datetime | None = None
    source_report_id: str | None = None
    note: str | None = None


class UpdatePurchaseOrderStatusRequest(BaseModel):
    status: OrderStatus


class ReceivePurchaseOrderRequest(BaseModel):
    quantity_received: int = Field(gt=0)
    note: str | None = None


class SupplierScorecard(BaseModel):
    supplier_id: str
    supplier_name: str
    reliability_score: float
    configured_lead_time_days: int
    total_orders: int
    open_orders: int
    arrived_orders: int
    delayed_orders: int
    late_open_orders: int
    on_time_rate: float
    fill_rate: float
    average_delay_days: float
    open_order_value: float


class ForecastInsight(BaseModel):
    product_id: str
    sku: str
    product_name: str
    baseline_daily_demand: float
    forecast_daily_demand: float
    trend_direction: Literal["up", "down", "steady"]
    confidence: Literal["medium", "high"]
    recent_sales_average: float
    predicted_7d_demand: float
    predicted_30d_demand: float


class AnomalyInsight(BaseModel):
    anomaly_type: Literal["sales_spike", "supplier_delay", "cash_pressure"]
    severity: Literal["watch", "high", "critical"]
    title: str
    detail: str
    related_product_id: str | None = None
    related_supplier_id: str | None = None
    related_order_id: str | None = None


class AutoOrderResult(BaseModel):
    created_orders: list[PurchaseOrder]
    skipped_products: list[str]
    summary: str


AgentToolName = Literal[
    "inventory_risk_scan",
    "late_order_scan",
    "cash_replenishment_check",
    "draft_replenishment_orders",
]
AgentName = Literal[
    "operations_manager",
    "inventory_risk_agent",
    "supplier_delay_agent",
    "cash_replenishment_agent",
]


class AgentRunRequest(BaseModel):
    goal: str = Field(
        default="Monitor today's inventory risks, late orders, cash pressure, and safe replenishment actions.",
        min_length=8,
        max_length=240,
    )
    agent_name: AgentName = "operations_manager"
    allow_order_drafts: bool = False


class AgentStepResult(BaseModel):
    step_id: str = Field(default_factory=new_id)
    agent_name: AgentName = "operations_manager"
    tool_name: AgentToolName
    status: Literal["completed", "skipped", "blocked"]
    summary: str
    details: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="after")
    def normalize_created_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class AgentRunResponse(BaseModel):
    run_id: str = Field(default_factory=new_id)
    business_id: str
    agent_name: AgentName = "operations_manager"
    goal: str
    status: Literal["completed", "blocked", "failed"]
    summary: str
    steps: list[AgentStepResult]
    created_orders: list[PurchaseOrder] = Field(default_factory=list)
    guardrail_notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", "completed_at", mode="after")
    def normalize_datetimes(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ChatRequest(BaseModel):
    message: str = Field(min_length=2)


class ChatResponse(BaseModel):
    answer: str
    used_ai: bool
    confidence: Literal["low", "medium", "high"] = "medium"
    refused: bool = False
    refusal_reason: str | None = None


class MorningBriefResponse(BaseModel):
    summary: str
    priorities: list[str]
    used_ai: bool
    confidence: Literal["low", "medium", "high"] = "medium"


class ScenarioAnalysisResponse(BaseModel):
    scenario_cash: float
    summary: str
    recommended_skus: list[str]
    deferred_skus: list[str]
    used_ai: bool
    confidence: Literal["low", "medium", "high"] = "medium"


class ReportComparisonResponse(BaseModel):
    latest_report_id: str | None = None
    previous_report_id: str | None = None
    summary: str
    changes: list[str]
    used_ai: bool
    confidence: Literal["low", "medium", "high"] = "medium"


class ScenarioRequest(BaseModel):
    cash: float = Field(ge=0)


class UpdateBusinessSettingsRequest(BaseModel):
    ai_enabled: bool | None = None
    ai_automation_enabled: bool | None = None
    notification_email: str | None = None
    critical_alerts_enabled: bool | None = None

    @field_validator("notification_email")
    def validate_notification_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Notification email must be a valid email address")
        return normalized


class AIAuditLog(BaseModel):
    audit_id: str = Field(default_factory=new_id)
    business_id: str
    feature: Literal["chat", "report", "brief", "scenario", "comparison", "agent"]
    used_ai: bool
    status: Literal["accepted", "fallback", "refused"]
    input_preview: str
    output_preview: str | None = None
    confidence: Literal["low", "medium", "high"] | None = None
    reason: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="after")
    def normalize_created_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class OrderNotificationEvent(BaseModel):
    event_id: str
    business_id: str
    order_id: str
    sku: str
    recipient_email: str | None = None
    placed_by_type: Literal["user", "llm", "system"]
    placed_by_label: str | None = None
    status: Literal["sent", "failed"]
    detail: str
    created_at: datetime

    @field_validator("created_at", mode="after")
    def normalize_created_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class TestNotificationResponse(BaseModel):
    sent: bool
    recipient_email: str | None = None
    detail: str
