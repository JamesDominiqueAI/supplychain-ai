from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from pydantic import BaseModel, Field, ValidationError

from guardrails import validate_chat_input
from notifications import EmailAlertService
from services import ReplenishmentService
from schemas import (
    AIAuditLog,
    AgentName,
    AgentRunRequest,
    AgentRunResponse,
    AgentStepResult,
    AnalysisJob,
    AnomalyInsight,
    AutoOrderResult,
    Business,
    ChatResponse,
    CreateInventoryMovementRequest,
    CreateProductRequest,
    CreatePurchaseOrderRequest,
    CreateSupplierRequest,
    ForecastInsight,
    InventoryHealthItem,
    InventoryMovement,
    MorningBriefResponse,
    OrderNotificationEvent,
    Product,
    PurchaseOrder,
    ReceivePurchaseOrderRequest,
    ReplenishmentReport,
    ReportComparisonResponse,
    ScenarioAnalysisResponse,
    ScenarioRequest,
    Supplier,
    SupplierScorecard,
    TestNotificationResponse,
    UpdateBusinessSettingsRequest,
    UpdatePurchaseOrderStatusRequest,
)


logger = logging.getLogger(__name__)

DEFAULT_BUSINESS_NAME = "Lakay Business"
LEGACY_DEFAULT_BUSINESS_NAMES = {"SupplyChain Workspace"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    return utc_now().isoformat()


class WorkspaceState(BaseModel):
    business: Business | None = None
    products: list[Product] = Field(default_factory=list)
    suppliers: list[Supplier] = Field(default_factory=list)
    movements: list[InventoryMovement] = Field(default_factory=list)
    jobs: list[AnalysisJob] = Field(default_factory=list)
    reports: list[ReplenishmentReport] = Field(default_factory=list)
    orders: list[PurchaseOrder] = Field(default_factory=list)
    agent_runs: list[AgentRunResponse] = Field(default_factory=list)
    ai_audit_logs: list[AIAuditLog] = Field(default_factory=list)
    order_notification_events: list[OrderNotificationEvent] = Field(default_factory=list)
    critical_alert_state: dict[str, dict[str, str | None]] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=utc_now)


class DynamoDBStore:
    """Persistent per-user store backed by a single DynamoDB document item."""

    def __init__(self, owner_user_id: str) -> None:
        self.owner_user_id = owner_user_id
        self.table_name = os.getenv("DYNAMODB_TABLE_NAME", "supplychain-ai-workspaces")
        self.region_name = os.getenv("DEFAULT_AWS_REGION", "us-east-1")
        self.endpoint_url = os.getenv("DYNAMODB_ENDPOINT_URL") or None
        self._prefer_local_mode = self._should_prefer_local_mode()
        self._dynamodb = boto3.resource(
            "dynamodb",
            region_name=self.region_name,
            endpoint_url=self.endpoint_url,
            config=Config(
                connect_timeout=1,
                read_timeout=2,
                retries={"max_attempts": 1, "mode": "standard"},
            ),
        )
        self._table = self._dynamodb.Table(self.table_name)
        self._storage_mode = "dynamodb"
        self._local_state_path = Path(
            os.getenv("LOCAL_STATE_PATH")
            or Path(__file__).resolve().parents[3] / "data" / "workspaces" / f"{self.owner_user_id}.json"
        )
        self.replenishment_service = ReplenishmentService()
        self.email_alerts = EmailAlertService()
        self._is_seeding = False
        self._initialize_storage()
        self.state = self._load_state()
        if self.state.business is None:
            self.business = Business(name=DEFAULT_BUSINESS_NAME)
            self.state.business = self.business
            self._save_state()
        else:
            self.business = self.state.business
            if self._migrate_legacy_default_business_name():
                self._save_state()
        self._seed()

    def _migrate_legacy_default_business_name(self) -> bool:
        if self.business.name not in LEGACY_DEFAULT_BUSINESS_NAMES:
            return False
        self.business.name = DEFAULT_BUSINESS_NAME
        self.state.business = self.business
        return True

    def _initialize_storage(self) -> None:
        if self._prefer_local_mode:
            self._storage_mode = "file"
            self._local_state_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info("Using local JSON workspace store for development mode.")
            return
        try:
            self._ensure_table()
        except Exception as exc:
            if self._should_fallback_to_file():
                self._storage_mode = "file"
                self._local_state_path.parent.mkdir(parents=True, exist_ok=True)
                logger.warning(
                    "Falling back to local JSON workspace store because DynamoDB is unavailable: %s",
                    exc,
                )
                return
            raise

    def _should_prefer_local_mode(self) -> bool:
        if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            return False
        explicit = os.getenv("DYNAMODB_USE_REMOTE", "").strip().lower()
        if explicit in {"1", "true", "yes"}:
            return False
        if explicit in {"0", "false", "no"}:
            return True

        explicit_local = os.getenv("DYNAMODB_USE_LOCAL", "").strip().lower()
        if explicit_local in {"1", "true", "yes"}:
            return True
        if explicit_local in {"0", "false", "no"}:
            return False

        environment = (
            os.getenv("APP_ENV")
            or os.getenv("ENVIRONMENT")
            or os.getenv("NODE_ENV")
            or "development"
        ).strip().lower()
        return environment in {"development", "dev", "local", "test"}

    def _should_fallback_to_file(self) -> bool:
        if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            return False
        fallback_default = "true" if self._should_prefer_local_mode() else "false"
        fallback_flag = os.getenv("DYNAMODB_FALLBACK_TO_FILE", fallback_default).strip().lower()
        return fallback_flag != "false"

    def _ensure_table(self) -> None:
        auto_create = os.getenv("DYNAMODB_AUTO_CREATE", "true").lower() == "true"
        client = self._dynamodb.meta.client
        try:
            client.describe_table(TableName=self.table_name)
        except client.exceptions.ResourceNotFoundException:
            if not auto_create:
                raise
            client.create_table(
                TableName=self.table_name,
                KeySchema=[{"AttributeName": "owner_user_id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "owner_user_id", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
            client.get_waiter("table_exists").wait(TableName=self.table_name)

    def _load_state(self) -> WorkspaceState:
        if self._storage_mode == "file":
            if not self._local_state_path.exists():
                return WorkspaceState()
            try:
                raw_content = self._local_state_path.read_text(encoding="utf-8")
                if not raw_content.strip():
                    raise JSONDecodeError("Workspace state file is empty", raw_content, 0)
                payload = json.loads(raw_content)
                return WorkspaceState.model_validate(payload)
            except (JSONDecodeError, ValidationError) as exc:
                backup_path = self._local_state_path.with_suffix(
                    f"{self._local_state_path.suffix or '.json'}.corrupt-{utc_now().strftime('%Y%m%d%H%M%S')}"
                )
                self._local_state_path.replace(backup_path)
                logger.warning(
                    "Recovered from corrupt local workspace state for %s. Backed up %s to %s: %s",
                    self.owner_user_id,
                    self._local_state_path,
                    backup_path,
                    exc,
                )
                return WorkspaceState()
        item = self._table.get_item(Key={"owner_user_id": self.owner_user_id}).get("Item")
        if not item or not item.get("state_json"):
            return WorkspaceState()
        payload = json.loads(item["state_json"])
        return WorkspaceState.model_validate(payload)

    def _save_state(self) -> None:
        self.state.updated_at = utc_now()
        if self._storage_mode == "file":
            self._local_state_path.parent.mkdir(parents=True, exist_ok=True)
            serialized = json.dumps(self.state.model_dump(mode="json"), indent=2)
            suffix = self._local_state_path.suffix or ".json"
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._local_state_path.parent,
                prefix=f"{self._local_state_path.stem}.",
                suffix=f"{suffix}.tmp",
                delete=False,
            ) as temp_file:
                temp_file.write(serialized)
                temp_path = Path(temp_file.name)
            temp_path.replace(self._local_state_path)
            return
        self._table.put_item(
            Item={
                "owner_user_id": self.owner_user_id,
                "business_id": self.business.business_id,
                "updated_at": self.state.updated_at.isoformat(),
                "state_json": json.dumps(self.state.model_dump(mode="json")),
            }
        )

    def _state_product(self, product_id: str) -> Product:
        for product in self.state.products:
            if product.product_id == product_id:
                return product
        raise KeyError(product_id)

    def _state_supplier(self, supplier_id: str | None) -> Supplier | None:
        if not supplier_id:
            return None
        for supplier in self.state.suppliers:
            if supplier.supplier_id == supplier_id:
                return supplier
        raise KeyError(supplier_id)

    def _state_order(self, order_id: str) -> PurchaseOrder:
        for order in self.state.orders:
            if order.order_id == order_id:
                return self._refresh_order_timeliness(order)
        raise KeyError(order_id)

    def _refresh_order_timeliness(self, order: PurchaseOrder) -> PurchaseOrder:
        late_open_statuses = {"approved", "placed", "in_transit", "partially_received", "delayed"}
        order.is_late = False
        order.days_late = 0
        if order.expected_delivery_date and order.status in late_open_statuses:
            order.days_late = max((utc_now().date() - order.expected_delivery_date.date()).days, 0)
            order.is_late = order.days_late > 0
        return order

    def _risk_level_for_product(self, product: Product) -> str:
        days_of_cover = product.current_stock / product.avg_daily_demand if product.avg_daily_demand > 0 else 999.0
        if product.current_stock <= max(1, product.reorder_point // 2):
            return "critical"
        if product.current_stock <= product.reorder_point:
            return "high"
        if days_of_cover <= product.lead_time_days:
            return "watch"
        return "healthy"

    def _health_item_for_product(self, product: Product) -> InventoryHealthItem:
        days_of_cover = product.current_stock / product.avg_daily_demand if product.avg_daily_demand > 0 else 999.0
        return InventoryHealthItem(
            product_id=product.product_id,
            sku=product.sku,
            product_name=product.name,
            current_stock=product.current_stock,
            reorder_point=product.reorder_point,
            days_of_cover=round(days_of_cover, 1),
            lead_time_days=product.lead_time_days,
            risk_level=self._risk_level_for_product(product),
        )

    def _record_ai_audit(
        self,
        *,
        feature: str,
        used_ai: bool,
        status: str,
        input_preview: str,
        output_preview: str | None = None,
        confidence: str | None = None,
        reason: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        audit = AIAuditLog(
            business_id=self.business.business_id,
            feature=feature,
            used_ai=used_ai,
            status=status,
            input_preview=input_preview[:400],
            output_preview=output_preview[:400] if output_preview else None,
            confidence=confidence,
            reason=reason[:400] if reason else None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
        self.state.ai_audit_logs.insert(0, audit)
        self.state.ai_audit_logs = self.state.ai_audit_logs[:200]
        self._save_state()

    def list_ai_audit_logs(self, limit: int = 50) -> list[AIAuditLog]:
        safe_limit = max(1, min(limit, 200))
        return sorted(self.state.ai_audit_logs, key=lambda item: item.created_at, reverse=True)[:safe_limit]

    def _record_order_notification_event(
        self,
        *,
        order: PurchaseOrder,
        recipient_email: str | None,
        status: str,
        detail: str,
    ) -> None:
        event = OrderNotificationEvent(
            event_id=f"order-email-{order.order_id}-{int(utc_now().timestamp() * 1000)}",
            business_id=self.business.business_id,
            order_id=order.order_id,
            sku=order.sku,
            recipient_email=recipient_email,
            placed_by_type=order.placed_by_type,
            placed_by_label=order.placed_by_label,
            status=status,
            detail=detail[:500],
            created_at=utc_now(),
        )
        self.state.order_notification_events.insert(0, event)
        self.state.order_notification_events = self.state.order_notification_events[:100]
        self._save_state()

    def list_order_notification_events(self) -> list[OrderNotificationEvent]:
        return sorted(self.state.order_notification_events, key=lambda item: item.created_at, reverse=True)[:25]

    def _send_order_placement_email_to_recipient(
        self,
        *,
        order: PurchaseOrder,
        product: Product,
        recipient_email: str | None,
    ) -> None:
        if self._is_seeding:
            return
        delivered, detail = self.email_alerts.send_order_placed_alert(
            business=self.business,
            recipient_email=recipient_email,
            sku=order.sku,
            product_name=order.product_name,
            product_category=product.category,
            quantity=order.quantity,
            estimated_cost=order.estimated_cost,
            supplier_name=order.supplier_name,
            placed_by_type=order.placed_by_type,
            placed_by_label=order.placed_by_label,
        )
        self._record_order_notification_event(
            order=order,
            recipient_email=recipient_email,
            status="sent" if delivered else "failed",
            detail=detail,
        )

    def _order_notification_recipients(self, extra_email: str | None = None) -> list[str]:
        recipients: list[str] = []
        for email in (self.business.notification_email, extra_email):
            normalized = (email or "").strip()
            if normalized and normalized.lower() not in {item.lower() for item in recipients}:
                recipients.append(normalized)
        return recipients

    def _send_order_placement_email(self, *, order: PurchaseOrder, product: Product, recipient_email: str | None = None) -> None:
        recipients = self._order_notification_recipients(recipient_email)
        if not recipients:
            self._send_order_placement_email_to_recipient(
                order=order,
                product=product,
                recipient_email=None,
            )
            return
        for target_email in recipients:
            self._send_order_placement_email_to_recipient(
                order=order,
                product=product,
                recipient_email=target_email,
            )

    def retry_failed_order_notifications(self, *, recipient_email: str | None = None) -> list[OrderNotificationEvent]:
        failed_events = [
            event
            for event in self.state.order_notification_events
            if event.status == "failed"
        ][:10]
        for event in failed_events:
            order = next((item for item in self.state.orders if item.order_id == event.order_id), None)
            if not order:
                continue
            product = self._state_product(order.product_id)
            self._send_order_placement_email_to_recipient(
                order=order,
                product=product,
                recipient_email=recipient_email or event.recipient_email or self.business.notification_email,
            )
        return self.list_order_notification_events()

    def _record_critical_alert_event(self, **_: Any) -> None:
        return

    def _sync_critical_alert_state(
        self,
        *,
        product: Product,
        previous_risk_level: str,
        trigger_source: str,
    ) -> None:
        health_item = self._health_item_for_product(product)
        current_risk_level = health_item.risk_level
        previous_state = self.state.critical_alert_state.get(product.product_id, {})
        last_alerted_at = previous_state.get("last_alerted_at")
        if current_risk_level != "critical":
            last_alerted_at = None
        self.state.critical_alert_state[product.product_id] = {
            "last_risk_level": current_risk_level,
            "last_alerted_at": last_alerted_at,
        }
        self._save_state()

        if previous_risk_level == "critical" or current_risk_level != "critical":
            return
        if self._is_seeding:
            return
        if not self.business.critical_alerts_enabled:
            self._record_critical_alert_event(
                product=product,
                recipient_email=self.business.notification_email,
                risk_level=current_risk_level,
                trigger_source=trigger_source,
                status="skipped",
                detail="Critical alerts are disabled in workspace settings.",
            )
            return

        delivered, detail = self.email_alerts.send_critical_stock_alert(
            business=self.business,
            product=product,
            health_item=health_item,
            recipient_email=self.business.notification_email,
            trigger_source=trigger_source,
        )
        if delivered:
            self.state.critical_alert_state[product.product_id]["last_alerted_at"] = utcnow_iso()
            self._save_state()
        self._record_critical_alert_event(
            product=product,
            recipient_email=self.business.notification_email,
            risk_level=current_risk_level,
            trigger_source=trigger_source,
            status="sent" if delivered else "failed",
            detail=detail,
        )

    def _set_product_preferred_supplier(self, product_id: str, supplier_id: str | None) -> None:
        product = self._state_product(product_id)
        product.preferred_supplier_id = supplier_id
        self._save_state()

    def _seed(self) -> None:
        self._is_seeding = True
        try:
            existing_products = {product.sku: product for product in self.list_products()}
            existing_suppliers = {supplier.name: supplier for supplier in self.list_suppliers()}

            supplier_specs = [
                CreateSupplierRequest(
                    name="Caribbean Staples Import",
                    contact_phone="+509-3700-1000",
                    lead_time_days=10,
                    reliability_score=0.72,
                    notes="Good prices but delivery timing fluctuates in rainy season.",
                ),
                CreateSupplierRequest(
                    name="Metro Household Wholesale",
                    contact_phone="+509-3700-2000",
                    lead_time_days=6,
                    reliability_score=0.9,
                    notes="Reliable but slightly more expensive.",
                ),
                CreateSupplierRequest(
                    name="Port-au-Prince Bulk Foods",
                    contact_phone="+509-3700-3000",
                    lead_time_days=8,
                    reliability_score=0.84,
                    notes="Balanced pricing and usually available inventory.",
                ),
                CreateSupplierRequest(
                    name="Island Consumer Goods",
                    contact_phone="+509-3700-4000",
                    lead_time_days=5,
                    reliability_score=0.88,
                    notes="Fast-moving household goods supplier.",
                ),
                CreateSupplierRequest(
                    name="Northern Farm Co-op",
                    contact_phone="+509-3700-5000",
                    lead_time_days=12,
                    reliability_score=0.79,
                    notes="Longer lead times but dependable for staples.",
                ),
            ]

            for spec in supplier_specs:
                if spec.name not in existing_suppliers:
                    existing_suppliers[spec.name] = self.create_supplier(spec)

            product_specs = [
                CreateProductRequest(
                    sku="RICE-25KG",
                    name="Imported Rice 25kg",
                    category="Staples",
                    reorder_point=20,
                    target_days_of_cover=21,
                    lead_time_days=10,
                    current_stock=18,
                    avg_daily_demand=3.5,
                    unit_cost=2600.0,
                    preferred_supplier_id=existing_suppliers["Caribbean Staples Import"].supplier_id,
                ),
                CreateProductRequest(
                    sku="OIL-1L",
                    name="Cooking Oil 1L",
                    category="Groceries",
                    reorder_point=30,
                    target_days_of_cover=14,
                    lead_time_days=8,
                    current_stock=65,
                    avg_daily_demand=4.0,
                    unit_cost=350.0,
                    preferred_supplier_id=existing_suppliers["Port-au-Prince Bulk Foods"].supplier_id,
                ),
                CreateProductRequest(
                    sku="SOAP-BAR",
                    name="Laundry Soap Bar",
                    category="Household",
                    reorder_point=40,
                    target_days_of_cover=18,
                    lead_time_days=6,
                    current_stock=25,
                    avg_daily_demand=5.5,
                    unit_cost=95.0,
                    preferred_supplier_id=existing_suppliers["Island Consumer Goods"].supplier_id,
                ),
                CreateProductRequest(
                    sku="SARDINE-TIN",
                    name="Sardine Tin",
                    category="Groceries",
                    reorder_point=50,
                    target_days_of_cover=20,
                    lead_time_days=7,
                    current_stock=72,
                    avg_daily_demand=6.0,
                    unit_cost=140.0,
                    preferred_supplier_id=existing_suppliers["Port-au-Prince Bulk Foods"].supplier_id,
                ),
                CreateProductRequest(
                    sku="BEANS-RED",
                    name="Red Beans Sack",
                    category="Staples",
                    reorder_point=16,
                    target_days_of_cover=25,
                    lead_time_days=12,
                    current_stock=11,
                    avg_daily_demand=1.8,
                    unit_cost=1800.0,
                    preferred_supplier_id=existing_suppliers["Northern Farm Co-op"].supplier_id,
                ),
                CreateProductRequest(
                    sku="SUGAR-2KG",
                    name="Sugar 2kg",
                    category="Groceries",
                    reorder_point=24,
                    target_days_of_cover=18,
                    lead_time_days=9,
                    current_stock=29,
                    avg_daily_demand=2.7,
                    unit_cost=420.0,
                    preferred_supplier_id=existing_suppliers["Metro Household Wholesale"].supplier_id,
                ),
            ]

            for spec in product_specs:
                if spec.sku not in existing_products:
                    existing_products[spec.sku] = self.create_product(spec)
                else:
                    self._set_product_preferred_supplier(
                        existing_products[spec.sku].product_id,
                        spec.preferred_supplier_id,
                    )

            if len(self.list_inventory_movements()) == 0:
                seed_movements = [
                    ("RICE-25KG", "sale", 12, "Weekly sales sample"),
                    ("OIL-1L", "sale", 18, "Weekly sales sample"),
                    ("SOAP-BAR", "sale", 22, "Weekly sales sample"),
                    ("SARDINE-TIN", "sale", 14, "Busy weekend demand"),
                    ("BEANS-RED", "sale", 5, "School market day"),
                    ("SUGAR-2KG", "sale", 7, "Retail counter sales"),
                ]
                for sku, movement_type, quantity, note in seed_movements:
                    self.add_inventory_movement(
                        CreateInventoryMovementRequest(
                            product_id=existing_products[sku].product_id,
                            movement_type=movement_type,
                            quantity=quantity,
                            note=note,
                        )
                    )

            if len(self.list_orders()) == 0:
                sardine = existing_products["SARDINE-TIN"]
                default_supplier_id = existing_suppliers["Port-au-Prince Bulk Foods"].supplier_id
                order = self.create_purchase_order(
                    CreatePurchaseOrderRequest(
                        product_id=sardine.product_id,
                        quantity=40,
                        supplier_id=default_supplier_id,
                        expected_delivery_date=utc_now(),
                        note="Initial seeded order",
                    ),
                    placed_by_type="system",
                    placed_by_label="Initial workspace seed",
                )
                self.update_purchase_order_status(
                    order.order_id,
                    UpdatePurchaseOrderStatusRequest(status="in_transit"),
                )

            if len(self.list_reports()) == 0:
                self.run_replenishment_job()
        finally:
            self._is_seeding = False

    def get_business(self) -> Business:
        return self.business

    def update_business_settings(self, request: UpdateBusinessSettingsRequest) -> Business:
        updates = request.model_dump(exclude_none=True)
        for field_name, value in updates.items():
            setattr(self.business, field_name, value)
        self.state.business = self.business
        self._save_state()
        return self.business

    def list_products(self) -> list[Product]:
        return sorted(self.state.products, key=lambda product: product.name)

    def create_product(self, request: CreateProductRequest) -> Product:
        product = Product(business_id=self.business.business_id, **request.model_dump())
        self.state.products.append(product)
        self.state.critical_alert_state[product.product_id] = {
            "last_risk_level": self._risk_level_for_product(product),
            "last_alerted_at": None,
        }
        self._save_state()
        return product

    def list_suppliers(self) -> list[Supplier]:
        return sorted(self.state.suppliers, key=lambda supplier: supplier.name)

    def create_supplier(self, request: CreateSupplierRequest) -> Supplier:
        supplier = Supplier(business_id=self.business.business_id, **request.model_dump())
        self.state.suppliers.append(supplier)
        self._save_state()
        return supplier

    def list_supplier_scorecards(self) -> list[SupplierScorecard]:
        suppliers = self.list_suppliers()
        orders = self.list_orders()
        scorecards: list[SupplierScorecard] = []

        for supplier in suppliers:
            supplier_orders = [order for order in orders if order.supplier_id == supplier.supplier_id]
            total_orders = len(supplier_orders)
            open_orders = len([order for order in supplier_orders if order.status not in {"arrived", "canceled"}])
            arrived_orders = len([order for order in supplier_orders if order.status == "arrived"])
            delayed_orders = len([order for order in supplier_orders if order.status == "delayed"])
            late_open_orders = len([order for order in supplier_orders if order.is_late])
            total_quantity = sum(order.quantity for order in supplier_orders)
            received_quantity = sum(order.received_quantity for order in supplier_orders)
            fill_rate = round(received_quantity / total_quantity, 2) if total_quantity else 0.0
            on_time_arrivals = len(
                [
                    order
                    for order in supplier_orders
                    if order.status == "arrived" and order.expected_delivery_date and order.days_late == 0
                ]
            )
            on_time_rate = round(on_time_arrivals / arrived_orders, 2) if arrived_orders else 0.0
            late_order_count = len([order for order in supplier_orders if order.days_late > 0])
            average_delay_days = (
                round(sum(order.days_late for order in supplier_orders if order.days_late > 0) / late_order_count, 1)
                if late_order_count
                else 0.0
            )
            open_order_value = round(
                sum(order.estimated_cost for order in supplier_orders if order.status not in {"arrived", "canceled"}),
                2,
            )
            scorecards.append(
                SupplierScorecard(
                    supplier_id=supplier.supplier_id,
                    supplier_name=supplier.name,
                    reliability_score=supplier.reliability_score,
                    configured_lead_time_days=supplier.lead_time_days,
                    total_orders=total_orders,
                    open_orders=open_orders,
                    arrived_orders=arrived_orders,
                    delayed_orders=delayed_orders,
                    late_open_orders=late_open_orders,
                    on_time_rate=on_time_rate,
                    fill_rate=fill_rate,
                    average_delay_days=average_delay_days,
                    open_order_value=open_order_value,
                )
            )

        return sorted(scorecards, key=lambda item: (-item.late_open_orders, item.on_time_rate, -item.open_order_value))

    def add_inventory_movement(self, request: CreateInventoryMovementRequest) -> InventoryMovement:
        product = self._state_product(request.product_id)
        previous_risk_level = self._risk_level_for_product(product)
        movement = InventoryMovement(
            business_id=self.business.business_id,
            product_id=request.product_id,
            movement_type=request.movement_type,
            quantity=request.quantity,
            note=request.note,
        )
        if request.movement_type == "sale":
            product.current_stock = max(0, product.current_stock - request.quantity)
        elif request.movement_type == "purchase":
            product.current_stock += request.quantity
        else:
            product.current_stock = request.quantity
        self.state.movements.append(movement)
        self._save_state()
        self._sync_critical_alert_state(
            product=product,
            previous_risk_level=previous_risk_level,
            trigger_source=request.movement_type,
        )
        return movement

    def list_inventory_movements(self) -> list[InventoryMovement]:
        return sorted(self.state.movements, key=lambda movement: movement.occurred_at, reverse=True)

    def list_forecast_insights(self) -> list[ForecastInsight]:
        movements = self.list_inventory_movements()
        insights: list[ForecastInsight] = []
        for product in self.list_products():
            forecast_daily, trend_direction, confidence, recent_average = self.replenishment_service._forecast_daily_demand(
                product,
                movements,
            )
            insights.append(
                ForecastInsight(
                    product_id=product.product_id,
                    sku=product.sku,
                    product_name=product.name,
                    baseline_daily_demand=round(product.avg_daily_demand, 2),
                    forecast_daily_demand=round(forecast_daily, 2),
                    trend_direction=trend_direction,
                    confidence=confidence,
                    recent_sales_average=round(recent_average, 2),
                    predicted_7d_demand=round(forecast_daily * 7, 1),
                    predicted_30d_demand=round(forecast_daily * 30, 1),
                )
            )
        return sorted(
            insights,
            key=lambda item: abs(item.forecast_daily_demand - item.baseline_daily_demand),
            reverse=True,
        )

    def list_anomaly_insights(self) -> list[AnomalyInsight]:
        anomalies: list[AnomalyInsight] = []
        movements = self.list_inventory_movements()
        orders = self.list_orders()
        reports = self.list_reports()
        latest_report = reports[0] if reports else None

        for product in self.list_products():
            sales = [
                movement.quantity
                for movement in movements
                if movement.product_id == product.product_id and movement.movement_type == "sale"
            ]
            if len(sales) >= 3:
                latest_sale = sales[0]
                baseline = sum(sales[1:]) / max(len(sales[1:]), 1)
                if baseline > 0 and latest_sale >= baseline * 1.8:
                    anomalies.append(
                        AnomalyInsight(
                            anomaly_type="sales_spike",
                            severity="high" if latest_sale < baseline * 2.3 else "critical",
                            title=f"Sales spike on {product.sku}",
                            detail=f"Latest sale movement was {latest_sale} units versus a recent baseline of {round(baseline, 1)} units.",
                            related_product_id=product.product_id,
                        )
                    )

        for order in orders:
            if order.is_late:
                anomalies.append(
                    AnomalyInsight(
                        anomaly_type="supplier_delay",
                        severity="critical" if order.days_late >= 4 else "high",
                        title=f"Late supplier order for {order.sku}",
                        detail=f"Order {order.order_id[:8]} from {order.supplier_name or 'unassigned supplier'} is late by {order.days_late} day(s).",
                        related_product_id=order.product_id,
                        related_supplier_id=order.supplier_id,
                        related_order_id=order.order_id,
                    )
                )

        if latest_report and latest_report.total_recommended_spend > self.business.available_cash:
            anomalies.append(
                AnomalyInsight(
                    anomaly_type="cash_pressure",
                    severity="high",
                    title="Recommended spend exceeds cash",
                    detail=f"Latest replenishment report recommends {latest_report.total_recommended_spend} {self.business.currency} against available cash of {self.business.available_cash}.",
                )
            )

        severity_rank = {"critical": 0, "high": 1, "watch": 2}
        return sorted(anomalies, key=lambda item: severity_rank[item.severity])

    def inventory_health(self) -> list[InventoryHealthItem]:
        items = [self._health_item_for_product(product) for product in self.list_products()]
        return sorted(items, key=lambda item: (item.risk_level, item.days_of_cover))

    def run_replenishment_job(self) -> AnalysisJob:
        job, report = self.replenishment_service.run(
            business=self.business,
            products=self.list_products(),
            movements=self.list_inventory_movements(),
        )
        audit_event = self.replenishment_service.narrator.last_audit_event
        if audit_event:
            self._record_ai_audit(**audit_event)
        self.state.jobs.insert(0, job)
        self.state.reports.insert(0, report)
        self._save_state()
        return job

    def auto_place_orders(self, *, recipient_email: str | None = None) -> AutoOrderResult:
        if not self.business.ai_enabled:
            return AutoOrderResult(
                created_orders=[],
                skipped_products=[],
                summary="AI is disabled in settings, so automatic order creation is blocked.",
            )
        if not self.business.ai_automation_enabled:
            return AutoOrderResult(
                created_orders=[],
                skipped_products=[],
                summary="AI automation is disabled. Enable it in Settings before placing automatic orders.",
            )
        _, report = self.replenishment_service.run(
            business=self.business,
            products=self.list_products(),
            movements=self.list_inventory_movements(),
        )

        open_orders_by_product = {
            order.product_id
            for order in self.list_orders()
            if order.status not in {"arrived", "canceled"}
        }
        created_orders: list[PurchaseOrder] = []
        skipped_products: list[str] = []
        spend_limit = min(
            self.business.available_cash,
            float(os.getenv("AI_AUTO_ORDER_MAX_SPEND", str(self.business.available_cash))),
        )
        planned_spend = 0.0
        draft_first = os.getenv("AI_AUTO_ORDER_DRAFT_FIRST", "true").strip().lower() != "false"

        for recommendation in report.recommendations:
            if recommendation.product_id in open_orders_by_product:
                skipped_products.append(recommendation.sku)
                continue
            if recommendation.recommendation_type not in {"buy_now", "split_order"}:
                skipped_products.append(recommendation.sku)
                continue
            if recommendation.urgency not in {"critical", "high"}:
                skipped_products.append(recommendation.sku)
                continue
            product = next((item for item in self.list_products() if item.product_id == recommendation.product_id), None)
            if not product or not product.preferred_supplier_id:
                skipped_products.append(recommendation.sku)
                continue
            quantity = recommendation.recommended_order_qty
            if recommendation.recommendation_type == "split_order":
                quantity = max(recommendation.recommended_order_qty // 2, 1)
            estimated_cost = round(quantity * product.unit_cost, 2)
            if planned_spend + estimated_cost > spend_limit:
                skipped_products.append(recommendation.sku)
                continue
            order = self.create_purchase_order(
                CreatePurchaseOrderRequest(
                    product_id=recommendation.product_id,
                    quantity=quantity,
                    supplier_id=product.preferred_supplier_id,
                    estimated_cost=estimated_cost,
                    source_report_id=report.report_id,
                    note=(
                        f"Auto-created as {'draft' if draft_first else 'placed'} "
                        f"from AI recommendation ({recommendation.recommendation_type})."
                    ),
                ),
                placed_by_type="llm",
                placed_by_label="LLM automation",
                recipient_email=recipient_email or self.business.notification_email,
                status="draft" if draft_first else "placed",
            )
            created_orders.append(order)
            open_orders_by_product.add(recommendation.product_id)
            planned_spend += estimated_cost

        summary = (
            f"Created {len(created_orders)} {'draft ' if draft_first else ''}automatic orders and skipped "
            f"{len(skipped_products)} products because they were lower priority, missing a supplier, "
            f"already had open orders, or exceeded the {spend_limit:.2f} {self.business.currency} automation budget."
        )
        return AutoOrderResult(
            created_orders=created_orders,
            skipped_products=sorted(set(skipped_products)),
            summary=summary,
        )

    def list_agent_runs(self, limit: int = 20) -> list[AgentRunResponse]:
        safe_limit = max(1, min(limit, 100))
        return sorted(self.state.agent_runs, key=lambda item: item.created_at, reverse=True)[:safe_limit]

    def _agent_step(
        self,
        agent_name: str,
        tool_name: str,
        status: str,
        summary: str,
        details: list[str] | None = None,
    ) -> AgentStepResult:
        return AgentStepResult(
            agent_name=agent_name,
            tool_name=tool_name,
            status=status,
            summary=summary,
            details=details or [],
        )

    def _persist_agent_run(
        self,
        run: AgentRunResponse,
        *,
        audit_status: str,
        used_ai: bool,
        reason: str,
    ) -> AgentRunResponse:
        self.state.agent_runs.insert(0, run)
        self.state.agent_runs = self.state.agent_runs[:100]
        self._record_ai_audit(
            feature="agent",
            used_ai=used_ai,
            status=audit_status,
            input_preview=run.goal,
            output_preview=run.summary,
            confidence="high",
            reason=reason,
        )
        self._save_state()
        return run

    def _agent_goal_is_allowed(self, goal: str) -> bool:
        normalized = goal.strip().lower()
        allowed_terms = {
            "inventory",
            "stock",
            "sku",
            "order",
            "orders",
            "supplier",
            "suppliers",
            "cash",
            "replenishment",
            "purchase",
            "risk",
            "late",
            "delay",
            "forecast",
            "warehouse",
            "business",
            "materials",
        }
        blocked_terms = {
            "call supplier",
            "phone supplier",
            "negotiate",
            "wire money",
            "bank transfer",
            "external purchase",
            "send payment",
        }
        return any(term in normalized for term in allowed_terms) and not any(term in normalized for term in blocked_terms)

    def _run_inventory_risk_agent(self, health: list[InventoryHealthItem]) -> tuple[list[AgentStepResult], list[InventoryHealthItem]]:
        risky_items = [item for item in health if item.risk_level in {"critical", "high", "watch"}]
        return [
            self._agent_step(
                "inventory_risk_agent",
                "inventory_risk_scan",
                "completed",
                f"Inventory Risk Agent found {len(risky_items)} item(s) needing attention.",
                [
                    f"{item.product_name} ({item.sku}): {item.current_stock} on hand, {item.days_of_cover} days cover, risk {item.risk_level}."
                    for item in risky_items[:5]
                ],
            )
        ], risky_items

    def _run_supplier_delay_agent(self, orders: list[PurchaseOrder]) -> tuple[list[AgentStepResult], list[PurchaseOrder]]:
        late_orders = [order for order in orders if order.is_late]
        return [
            self._agent_step(
                "supplier_delay_agent",
                "late_order_scan",
                "completed",
                f"Supplier Delay Agent found {len(late_orders)} late order(s).",
                [
                    f"{order.product_name} ({order.sku}) is late by {order.days_late} day(s), status {order.status.replace('_', ' ')}."
                    for order in late_orders[:5]
                ],
            )
        ], late_orders

    def _latest_report_for_agent(self) -> tuple[ReplenishmentReport | None, str]:
        latest_report = self.list_reports()[0] if self.list_reports() else None
        if latest_report is None:
            job = self.run_replenishment_job()
            latest_report = self.list_reports()[0] if self.list_reports() else None
            return latest_report, f"Generated replenishment report through job {job.job_id}."
        return latest_report, f"Used latest replenishment report {latest_report.report_id}."

    def _run_cash_replenishment_agent(
        self,
        latest_report: ReplenishmentReport | None,
        report_detail: str,
        *,
        allow_order_drafts: bool,
        recipient_email: str | None,
    ) -> tuple[list[AgentStepResult], list[PurchaseOrder]]:
        spend = latest_report.total_recommended_spend if latest_report else 0
        steps = [
            self._agent_step(
                "cash_replenishment_agent",
                "cash_replenishment_check",
                "completed",
                (
                    f"Cash Replenishment Agent checked {spend:g} {self.business.currency} recommended spend "
                    f"against {self.business.available_cash:g} {self.business.currency} available cash."
                ),
                [
                    report_detail,
                    "Cash pressure detected; split or defer lower-risk orders."
                    if spend > self.business.available_cash
                    else "Recommended spend fits available cash.",
                ],
            )
        ]

        created_orders: list[PurchaseOrder] = []
        if allow_order_drafts and self.business.ai_automation_enabled:
            auto_result = self.auto_place_orders(recipient_email=recipient_email)
            created_orders = auto_result.created_orders
            steps.append(
                self._agent_step(
                    "cash_replenishment_agent",
                    "draft_replenishment_orders",
                    "completed",
                    auto_result.summary,
                    [f"Drafted {order.quantity} units of {order.product_name} ({order.sku})." for order in created_orders[:5]],
                )
            )
        elif allow_order_drafts:
            steps.append(
                self._agent_step(
                    "cash_replenishment_agent",
                    "draft_replenishment_orders",
                    "blocked",
                    "Draft order creation was requested but AI automation is disabled.",
                    ["Enable AI Automation in Settings before the cash agent can draft orders."],
                )
            )
        else:
            steps.append(
                self._agent_step(
                    "cash_replenishment_agent",
                    "draft_replenishment_orders",
                    "skipped",
                    "Draft order creation was not requested for this run.",
                    ["The cash agent planned only; no orders were created."],
                )
            )
        return steps, created_orders

    def run_operations_agent(
        self,
        request: AgentRunRequest,
        *,
        recipient_email: str | None = None,
    ) -> AgentRunResponse:
        goal = request.goal.strip()
        agent_name: AgentName = request.agent_name
        guardrail_notes = [
            "Agent team tools are limited to internal workspace data and draft order creation.",
            "External supplier calls, payments, and off-platform purchasing are blocked.",
            "Operations Manager can coordinate Inventory Risk, Supplier Delay, and Cash Replenishment agents.",
        ]
        if not self.business.ai_enabled:
            guardrail_notes.append("AI is disabled, so the agent is blocked before planning.")
            run = AgentRunResponse(
                business_id=self.business.business_id,
                agent_name=agent_name,
                goal=goal,
                status="blocked",
                summary="Agent run blocked because AI is disabled in Settings.",
                steps=[],
                guardrail_notes=guardrail_notes,
            )
            return self._persist_agent_run(run, audit_status="refused", used_ai=False, reason="AI disabled.")

        if not self._agent_goal_is_allowed(goal):
            guardrail_notes.append("Goal is outside inventory operations or asks for unsupported external action.")
            run = AgentRunResponse(
                business_id=self.business.business_id,
                agent_name=agent_name,
                goal=goal,
                status="blocked",
                summary="Agent run blocked by allowed-topic guardrails.",
                steps=[],
                guardrail_notes=guardrail_notes,
            )
            return self._persist_agent_run(run, audit_status="refused", used_ai=False, reason="Unsupported agent goal.")

        steps: list[AgentStepResult] = []
        health = self.inventory_health()
        orders = self.list_orders()
        inventory_steps, risky_items = self._run_inventory_risk_agent(health)
        supplier_steps, late_orders = self._run_supplier_delay_agent(orders)
        latest_report, report_detail = self._latest_report_for_agent()
        created_orders: list[PurchaseOrder] = []
        if agent_name == "inventory_risk_agent":
            steps.extend(inventory_steps)
        elif agent_name == "supplier_delay_agent":
            steps.extend(supplier_steps)
        elif agent_name == "cash_replenishment_agent":
            cash_steps, created_orders = self._run_cash_replenishment_agent(
                latest_report,
                report_detail,
                allow_order_drafts=request.allow_order_drafts,
                recipient_email=recipient_email,
            )
            steps.extend(cash_steps)
        else:
            steps.append(
                self._agent_step(
                    "operations_manager",
                    "inventory_risk_scan",
                    "completed",
                    "Operations Manager delegated inventory risk scanning to the Inventory Risk Agent.",
                    [inventory_steps[0].summary],
                )
            )
            steps.extend(inventory_steps)
            steps.append(
                self._agent_step(
                    "operations_manager",
                    "late_order_scan",
                    "completed",
                    "Operations Manager delegated late-order monitoring to the Supplier Delay Agent.",
                    [supplier_steps[0].summary],
                )
            )
            steps.extend(supplier_steps)
            cash_steps, created_orders = self._run_cash_replenishment_agent(
                latest_report,
                report_detail,
                allow_order_drafts=request.allow_order_drafts,
                recipient_email=recipient_email,
            )
            steps.append(
                self._agent_step(
                    "operations_manager",
                    "cash_replenishment_check",
                    "completed",
                    "Operations Manager delegated cash and replenishment planning to the Cash Replenishment Agent.",
                    [cash_steps[0].summary],
                )
            )
            steps.extend(cash_steps)

        summary = (
            f"{agent_name.replace('_', ' ').title()} completed {len(steps)} tool step(s): {len(risky_items)} risky item(s), "
            f"{len(late_orders)} late order(s), and {len(created_orders)} draft order(s) created."
        )
        run = AgentRunResponse(
            business_id=self.business.business_id,
            agent_name=agent_name,
            goal=goal,
            status="completed",
            summary=summary,
            steps=steps,
            created_orders=created_orders,
            guardrail_notes=guardrail_notes,
        )
        return self._persist_agent_run(
            run,
            audit_status="accepted",
            used_ai=True,
            reason="Agent team executed bounded internal tools.",
        )

    def _rule_based_workspace_answer(
        self,
        *,
        health: list[InventoryHealthItem],
        orders: list[PurchaseOrder],
        latest_report: ReplenishmentReport | None,
        anomalies: list[AnomalyInsight],
        forecasts: list[ForecastInsight],
    ) -> str:
        risky_items = [item for item in health if item.risk_level in {"critical", "high", "watch"}][:5]
        late_orders = [item for item in orders if item.is_late][:5]
        lines: list[str] = []

        if risky_items:
            lines.append(f"Inventory risks to focus today: {len(risky_items)} item(s) need attention.")
            for index, item in enumerate(risky_items, start=1):
                forecast = next((entry for entry in forecasts if entry.product_id == item.product_id), None)
                recommendation = (
                    next((rec for rec in latest_report.recommendations if rec.product_id == item.product_id), None)
                    if latest_report
                    else None
                )
                demand_note = (
                    f" Forecast 7d demand is about {forecast.predicted_7d_demand:g} units with a {forecast.trend_direction} trend."
                    if forecast
                    else ""
                )
                order_note = (
                    f" Recommended order is {recommendation.recommended_order_qty} units, estimated at {recommendation.estimated_cost:g} {self.business.currency}."
                    if recommendation
                    else " Review reorder quantity before committing cash."
                )
                lines.append(
                    f"{index}) {item.product_name} ({item.sku}): {item.risk_level} risk, {item.current_stock} on hand, "
                    f"{item.days_of_cover:g} days of cover, reorder point {item.reorder_point}, lead time {item.lead_time_days} day(s)."
                    f"{demand_note}{order_note}"
                )
        else:
            lines.append("Inventory risks to focus today: no critical or high-risk products are active right now.")

        if late_orders:
            lines.append(f"Late orders: {len(late_orders)} open order(s) are late.")
            for index, order in enumerate(late_orders, start=1):
                lines.append(
                    f"{index}) {order.product_name} ({order.sku}): {order.quantity} units from "
                    f"{order.supplier_name or 'unassigned supplier'}, status {order.status.replace('_', ' ')}, "
                    f"late by {order.days_late} day(s). Follow up with the supplier or update the expected delivery date."
                )
        else:
            lines.append("Late orders: none currently.")

        if latest_report:
            lines.append(
                f"Cash check: latest recommended spend is {latest_report.total_recommended_spend:g} {self.business.currency} "
                f"against available cash of {self.business.available_cash:g} {self.business.currency}. "
                f"{'Prioritize only critical items and split orders.' if latest_report.total_recommended_spend > self.business.available_cash else 'The current plan fits available cash.'}"
            )
        else:
            lines.append(f"Cash check: available cash is {self.business.available_cash:g} {self.business.currency}. Generate a replenishment report for spend guidance.")

        if anomalies:
            lines.append("Additional signals: " + " ".join(f"{item.title}: {item.detail}" for item in anomalies[:3]))

        lines.append("Action plan: handle late orders first, then buy or draft orders for critical products, and delay lower-risk purchases if cash is tight.")
        return "\n".join(lines)

    def chat_answer(self, question: str) -> ChatResponse:
        input_guardrail = validate_chat_input(question)
        if not input_guardrail.allowed:
            self._record_ai_audit(
                feature="chat",
                used_ai=False,
                status="refused",
                input_preview=question,
                reason=input_guardrail.reason,
                confidence="low",
            )
            return ChatResponse(
                answer="I can help with inventory, suppliers, orders, cash, forecasts, reports, and delays inside this workspace.",
                used_ai=False,
                confidence="low",
                refused=True,
                refusal_reason=input_guardrail.reason,
            )

        latest_report = self.list_reports()[0] if self.list_reports() else None
        anomalies = self.list_anomaly_insights()
        forecasts = self.list_forecast_insights()[:5]
        scorecards = self.list_supplier_scorecards()[:5]
        orders = self.list_orders()
        health = self.inventory_health()

        snapshot = {
            "business": self.business.model_dump(mode="json"),
            "critical_items": [item.model_dump(mode="json") for item in health if item.risk_level == "critical"],
            "late_orders": [item.model_dump(mode="json") for item in orders if item.is_late],
            "latest_report": latest_report.model_dump(mode="json") if latest_report else None,
            "anomalies": [item.model_dump(mode="json") for item in anomalies[:6]],
            "forecasts": [item.model_dump(mode="json") for item in forecasts],
            "supplier_scorecards": [item.model_dump(mode="json") for item in scorecards],
        }

        ai_response = None
        if self.business.ai_enabled:
            ai_response = self.replenishment_service.narrator.answer_workspace_question(
                workspace_snapshot=snapshot,
                question=question,
            )
            audit_event = self.replenishment_service.narrator.last_audit_event
            if audit_event:
                self._record_ai_audit(**audit_event)
            if ai_response and not ai_response.get("refused") and ai_response.get("confidence") in {"medium", "high"}:
                return ChatResponse(
                    answer=ai_response["answer"].strip(),
                    used_ai=True,
                    confidence=ai_response.get("confidence", "medium"),
                    refused=False,
                    refusal_reason=None,
                )

        question_lower = question.lower()
        if "supplier" in question_lower and not any(term in question_lower for term in ("risk", "late", "delay", "stock", "inventory")):
            risky_supplier = scorecards[0] if scorecards else None
            answer = (
                f"The supplier needing the most attention is {risky_supplier.supplier_name}. It has {risky_supplier.late_open_orders} late open order(s) and {round(risky_supplier.on_time_rate * 100)}% on-time performance."
                if risky_supplier
                else "There is not enough supplier activity yet to rank supplier performance."
            )
        else:
            answer = self._rule_based_workspace_answer(
                health=health,
                orders=orders,
                latest_report=latest_report,
                anomalies=anomalies,
                forecasts=forecasts,
            )
        self._record_ai_audit(
            feature="chat",
            used_ai=False,
            status="fallback",
            input_preview=question,
            output_preview=answer,
            confidence="medium",
            reason="Rule-based fallback response.",
        )
        return ChatResponse(answer=answer, used_ai=False, confidence="medium")

    def get_rule_based_morning_brief(self) -> MorningBriefResponse:
        latest_report = self.list_reports()[0] if self.list_reports() else None
        health = self.inventory_health()
        orders = self.list_orders()
        anomalies = self.list_anomaly_insights()
        priorities: list[str] = []
        critical_items = [item for item in health if item.risk_level == "critical"]
        if critical_items:
            priorities.append(f"Review critical stock on {', '.join(item.sku for item in critical_items[:3])} before opening purchasing.")
        late_orders = [item for item in orders if item.is_late]
        if late_orders:
            priorities.append(f"Follow up on {len(late_orders)} late order(s), starting with {late_orders[0].sku}.")
        if latest_report:
            priorities.append(
                f"Latest replenishment run recommends {latest_report.recommendations[:1][0].sku if latest_report.recommendations else 'no SKUs'} as the top purchase focus."
            )
        if not priorities:
            priorities.append("No urgent stock or supplier issues are active right now.")
        summary = f"You have {len(critical_items)} critical item(s), {len(late_orders)} late order(s), and {len(anomalies)} anomaly signal(s) this morning."
        return MorningBriefResponse(summary=summary, priorities=priorities[:4], used_ai=False, confidence="medium")

    def get_morning_brief(self) -> MorningBriefResponse:
        latest_report = self.list_reports()[0] if self.list_reports() else None
        health = self.inventory_health()
        orders = self.list_orders()
        anomalies = self.list_anomaly_insights()
        forecasts = self.list_forecast_insights()[:5]
        snapshot = {
            "business": self.business.model_dump(mode="json"),
            "critical_items": [item.model_dump(mode="json") for item in health if item.risk_level == "critical"],
            "late_orders": [item.model_dump(mode="json") for item in orders if item.is_late],
            "latest_report": latest_report.model_dump(mode="json") if latest_report else None,
            "anomalies": [item.model_dump(mode="json") for item in anomalies[:6]],
            "forecasts": [item.model_dump(mode="json") for item in forecasts],
        }
        if self.business.ai_enabled:
            ai_brief = self.replenishment_service.narrator.create_morning_brief(workspace_snapshot=snapshot)
            audit_event = self.replenishment_service.narrator.last_audit_event
            if audit_event:
                self._record_ai_audit(**audit_event)
            if ai_brief:
                return MorningBriefResponse(
                    summary=ai_brief["summary"].strip(),
                    priorities=ai_brief["priorities"][:4],
                    used_ai=True,
                    confidence=ai_brief.get("confidence", "medium"),
                )
        return self.get_rule_based_morning_brief()

    def analyze_scenario(self, request: ScenarioRequest) -> ScenarioAnalysisResponse:
        latest_report = self.list_reports()[0] if self.list_reports() else None
        if not latest_report:
            return ScenarioAnalysisResponse(
                scenario_cash=request.cash,
                summary="Generate a replenishment report first before running a cash scenario.",
                recommended_skus=[],
                deferred_skus=[],
                used_ai=False,
                confidence="low",
            )
        sorted_recommendations = sorted(
            latest_report.recommendations,
            key=lambda item: (["critical", "high", "medium", "low"].index(item.urgency), -item.estimated_cost),
        )
        remaining_cash = request.cash
        recommended_skus: list[str] = []
        deferred_skus: list[str] = []
        for item in sorted_recommendations:
            if item.estimated_cost <= remaining_cash:
                recommended_skus.append(item.sku)
                remaining_cash -= item.estimated_cost
            else:
                deferred_skus.append(item.sku)

        if self.business.ai_enabled:
            ai_scenario = self.replenishment_service.narrator.analyze_cash_scenario(
                business=self.business,
                report=latest_report,
                scenario_cash=request.cash,
            )
            audit_event = self.replenishment_service.narrator.last_audit_event
            if audit_event:
                self._record_ai_audit(**audit_event)
            if ai_scenario:
                return ScenarioAnalysisResponse(
                    scenario_cash=request.cash,
                    summary=ai_scenario["summary"].strip(),
                    recommended_skus=ai_scenario["recommended_skus"][:6],
                    deferred_skus=ai_scenario["deferred_skus"][:6],
                    used_ai=True,
                    confidence=ai_scenario.get("confidence", "medium"),
                )

        summary = f"With {request.cash} {self.business.currency}, you can cover {len(recommended_skus)} recommendation(s) now and would defer {len(deferred_skus)}."
        return ScenarioAnalysisResponse(
            scenario_cash=request.cash,
            summary=summary,
            recommended_skus=recommended_skus[:6],
            deferred_skus=deferred_skus[:6],
            used_ai=False,
            confidence="medium",
        )

    def compare_latest_reports(self) -> ReportComparisonResponse:
        reports = self.list_reports()
        if len(reports) < 2:
            return ReportComparisonResponse(
                latest_report_id=reports[0].report_id if reports else None,
                previous_report_id=None,
                summary="Generate at least two replenishment reports to compare changes over time.",
                changes=[],
                used_ai=False,
                confidence="low",
            )
        latest_report = reports[0]
        previous_report = reports[1]
        latest_skus = {item.sku for item in latest_report.recommendations}
        previous_skus = {item.sku for item in previous_report.recommendations}
        introduced = sorted(latest_skus - previous_skus)
        resolved = sorted(previous_skus - latest_skus)
        spend_delta = round(latest_report.total_recommended_spend - previous_report.total_recommended_spend, 2)
        changes: list[str] = []
        if introduced:
            changes.append(f"New recommendation pressure appeared on {', '.join(introduced[:3])}.")
        if resolved:
            changes.append(f"Recommendation pressure eased on {', '.join(resolved[:3])}.")
        changes.append(f"Recommended spend changed by {spend_delta} {self.business.currency} compared with the prior run.")

        if self.business.ai_enabled:
            ai_comparison = self.replenishment_service.narrator.compare_reports(
                latest_report=latest_report,
                previous_report=previous_report,
            )
            audit_event = self.replenishment_service.narrator.last_audit_event
            if audit_event:
                self._record_ai_audit(**audit_event)
            if ai_comparison:
                return ReportComparisonResponse(
                    latest_report_id=latest_report.report_id,
                    previous_report_id=previous_report.report_id,
                    summary=ai_comparison["summary"].strip(),
                    changes=ai_comparison["changes"][:4],
                    used_ai=True,
                    confidence=ai_comparison.get("confidence", "medium"),
                )

        summary = f"The latest report recommends {len(latest_report.recommendations)} items versus {len(previous_report.recommendations)} in the prior run."
        return ReportComparisonResponse(
            latest_report_id=latest_report.report_id,
            previous_report_id=previous_report.report_id,
            summary=summary,
            changes=changes[:4],
            used_ai=False,
            confidence="medium",
        )

    def list_jobs(self) -> list[AnalysisJob]:
        return sorted(self.state.jobs, key=lambda job: job.created_at, reverse=True)

    def get_job(self, job_id: str) -> AnalysisJob | None:
        for job in self.state.jobs:
            if job.job_id == job_id:
                return job
        return None

    def list_reports(self) -> list[ReplenishmentReport]:
        return sorted(self.state.reports, key=lambda report: report.generated_at, reverse=True)

    def get_report(self, report_id: str) -> ReplenishmentReport | None:
        for report in self.state.reports:
            if report.report_id == report_id:
                return report
        return None

    def list_orders(self) -> list[PurchaseOrder]:
        refreshed = [self._refresh_order_timeliness(order) for order in self.state.orders]
        return sorted(refreshed, key=lambda order: order.created_at, reverse=True)

    def create_purchase_order(
        self,
        request: CreatePurchaseOrderRequest,
        *,
        placed_by_type: str = "user",
        placed_by_label: str | None = None,
        recipient_email: str | None = None,
        status: str = "placed",
    ) -> PurchaseOrder:
        product = self._state_product(request.product_id)
        supplier = self._state_supplier(request.supplier_id or product.preferred_supplier_id)
        estimated_cost = (
            round(request.estimated_cost, 2)
            if request.estimated_cost is not None
            else round(request.quantity * product.unit_cost, 2)
        )
        expected_delivery_date = request.expected_delivery_date
        if expected_delivery_date is None and supplier is not None:
            expected_delivery_date = utc_now() + timedelta(days=supplier.lead_time_days)
        order = PurchaseOrder(
            business_id=self.business.business_id,
            product_id=product.product_id,
            sku=product.sku,
            product_name=product.name,
            quantity=request.quantity,
            estimated_cost=estimated_cost,
            status=status,
            supplier_id=supplier.supplier_id if supplier else None,
            supplier_name=supplier.name if supplier else None,
            expected_delivery_date=expected_delivery_date,
            source_report_id=request.source_report_id,
            placed_by_type=placed_by_type,
            placed_by_label=placed_by_label,
            note=request.note,
        )
        self._refresh_order_timeliness(order)
        self.state.orders.append(order)
        self._save_state()
        if order.status == "placed":
            self._send_order_placement_email(order=order, product=product, recipient_email=recipient_email)
        return order

    def update_purchase_order_status(
        self,
        order_id: str,
        request: UpdatePurchaseOrderStatusRequest,
        *,
        recipient_email: str | None = None,
    ) -> PurchaseOrder:
        order = self._state_order(order_id)
        product = self._state_product(order.product_id)
        was_placed = order.status == "placed"
        order.status = request.status
        if request.status == "placed" and not was_placed and order.placed_by_type != "llm":
            order.placed_by_type = "user"
            order.placed_by_label = recipient_email or "You"
        order.updated_at = utc_now()
        self._refresh_order_timeliness(order)
        self._save_state()
        if request.status == "placed" and not was_placed:
            self._send_order_placement_email(order=order, product=product, recipient_email=recipient_email)
        return order

    def receive_purchase_order(
        self,
        order_id: str,
        request: ReceivePurchaseOrderRequest,
    ) -> PurchaseOrder:
        order = self._state_order(order_id)
        remaining_quantity = order.quantity - order.received_quantity
        quantity_to_receive = min(request.quantity_received, remaining_quantity)
        if quantity_to_receive <= 0:
            return order
        order.received_quantity += quantity_to_receive
        order.last_received_at = utc_now()
        order.updated_at = order.last_received_at
        order.status = "arrived" if order.received_quantity >= order.quantity else "partially_received"
        self._refresh_order_timeliness(order)
        self._save_state()

        receive_note = request.note or f"Purchase order {order.order_id} received"
        self.add_inventory_movement(
            CreateInventoryMovementRequest(
                product_id=order.product_id,
                movement_type="purchase",
                quantity=quantity_to_receive,
                note=receive_note,
            )
        )
        return order

    def send_test_order_notification(self, *, recipient_email: str | None = None) -> TestNotificationResponse:
        target_email = recipient_email or self.business.notification_email
        sample_product = self.list_products()[0] if self.list_products() else None
        sample_sku = sample_product.sku if sample_product else "TEST-ORDER"
        sample_name = sample_product.name if sample_product else "Test Product"
        sample_category = sample_product.category if sample_product else "Testing"
        sample_cost = round((sample_product.unit_cost if sample_product else 125.0) * 3, 2)
        test_order = PurchaseOrder(
            business_id=self.business.business_id,
            product_id=sample_product.product_id if sample_product else "test-product",
            sku=sample_sku,
            product_name=sample_name,
            quantity=3,
            estimated_cost=sample_cost,
            placed_by_type="user",
            placed_by_label=recipient_email or "You",
            note="Manual test order email from Settings",
        )
        delivered, detail = self.email_alerts.send_order_placed_alert(
            business=self.business,
            recipient_email=target_email,
            sku=test_order.sku,
            product_name=test_order.product_name,
            product_category=sample_category,
            quantity=test_order.quantity,
            estimated_cost=test_order.estimated_cost,
            supplier_name=None,
            placed_by_type=test_order.placed_by_type,
            placed_by_label=test_order.placed_by_label,
        )
        self._record_order_notification_event(
            order=test_order,
            recipient_email=target_email,
            status="sent" if delivered else "failed",
            detail=detail,
        )
        return TestNotificationResponse(sent=delivered, recipient_email=target_email, detail=detail)
