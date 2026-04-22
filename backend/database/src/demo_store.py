from __future__ import annotations

from datetime import datetime, timezone

from services import ReplenishmentService
from schemas import (
    AnalysisJob,
    Business,
    CreateInventoryMovementRequest,
    CreatePurchaseOrderRequest,
    CreateProductRequest,
    CreateSupplierRequest,
    InventoryHealthItem,
    InventoryMovement,
    Product,
    PurchaseOrder,
    Supplier,
    ReplenishmentReport,
    UpdatePurchaseOrderStatusRequest,
)


class DemoStore:
    """In-memory demo store for the starter implementation."""

    def __init__(self) -> None:
        self.business = Business(name="Kay Biznis Demo", available_cash=180000.0)
        self.products: dict[str, Product] = {}
        self.suppliers: dict[str, Supplier] = {}
        self.movements: list[InventoryMovement] = []
        self.jobs: dict[str, AnalysisJob] = {}
        self.reports: dict[str, ReplenishmentReport] = {}
        self.orders: dict[str, PurchaseOrder] = {}
        self.replenishment_service = ReplenishmentService()
        self._seed()

    def _seed(self) -> None:
        rice = self.create_product(
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
            )
        )
        oil = self.create_product(
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
            )
        )
        soap = self.create_product(
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
            )
        )

        self.create_supplier(
            CreateSupplierRequest(
                name="Caribbean Staples Import",
                contact_phone="+509-3700-1000",
                lead_time_days=10,
                reliability_score=0.72,
                notes="Good prices but delivery timing fluctuates in rainy season.",
            )
        )
        self.create_supplier(
            CreateSupplierRequest(
                name="Metro Household Wholesale",
                contact_phone="+509-3700-2000",
                lead_time_days=6,
                reliability_score=0.9,
                notes="Reliable but slightly more expensive.",
            )
        )

        self.add_inventory_movement(
            CreateInventoryMovementRequest(product_id=rice.product_id, movement_type="sale", quantity=12, note="Weekly sales sample")
        )
        self.add_inventory_movement(
            CreateInventoryMovementRequest(product_id=oil.product_id, movement_type="sale", quantity=18, note="Weekly sales sample")
        )
        self.add_inventory_movement(
            CreateInventoryMovementRequest(product_id=soap.product_id, movement_type="sale", quantity=22, note="Weekly sales sample")
        )

    def get_business(self) -> Business:
        return self.business

    def list_products(self) -> list[Product]:
        return sorted(self.products.values(), key=lambda product: product.name)

    def create_product(self, request: CreateProductRequest) -> Product:
        product = Product(business_id=self.business.business_id, **request.model_dump())
        self.products[product.product_id] = product
        return product

    def list_suppliers(self) -> list[Supplier]:
        return sorted(self.suppliers.values(), key=lambda supplier: supplier.name)

    def create_supplier(self, request: CreateSupplierRequest) -> Supplier:
        supplier = Supplier(business_id=self.business.business_id, **request.model_dump())
        self.suppliers[supplier.supplier_id] = supplier
        return supplier

    def add_inventory_movement(self, request: CreateInventoryMovementRequest) -> InventoryMovement:
        product = self.products[request.product_id]
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
        self.movements.append(movement)
        return movement

    def list_inventory_movements(self) -> list[InventoryMovement]:
        return sorted(self.movements, key=lambda movement: movement.occurred_at, reverse=True)

    def inventory_health(self) -> list[InventoryHealthItem]:
        items: list[InventoryHealthItem] = []
        for product in self.products.values():
            days_of_cover = product.current_stock / product.avg_daily_demand if product.avg_daily_demand > 0 else 999.0
            if product.current_stock <= max(1, product.reorder_point // 2):
                risk_level = "critical"
            elif product.current_stock <= product.reorder_point:
                risk_level = "high"
            elif days_of_cover <= product.lead_time_days:
                risk_level = "watch"
            else:
                risk_level = "healthy"

            items.append(
                InventoryHealthItem(
                    product_id=product.product_id,
                    sku=product.sku,
                    product_name=product.name,
                    current_stock=product.current_stock,
                    reorder_point=product.reorder_point,
                    days_of_cover=round(days_of_cover, 1),
                    lead_time_days=product.lead_time_days,
                    risk_level=risk_level,
                )
            )
        return sorted(items, key=lambda item: (item.risk_level, item.days_of_cover))

    def run_replenishment_job(self) -> AnalysisJob:
        job, report = self.replenishment_service.run(
            business=self.business,
            products=list(self.products.values()),
        )
        self.reports[report.report_id] = report
        self.jobs[job.job_id] = job
        return job

    def list_jobs(self) -> list[AnalysisJob]:
        return sorted(self.jobs.values(), key=lambda job: job.created_at, reverse=True)

    def get_job(self, job_id: str) -> AnalysisJob | None:
        return self.jobs.get(job_id)

    def list_reports(self) -> list[ReplenishmentReport]:
        return sorted(self.reports.values(), key=lambda report: report.generated_at, reverse=True)

    def get_report(self, report_id: str) -> ReplenishmentReport | None:
        return self.reports.get(report_id)

    def list_orders(self) -> list[PurchaseOrder]:
        return sorted(self.orders.values(), key=lambda order: order.created_at, reverse=True)

    def create_purchase_order(self, request: CreatePurchaseOrderRequest) -> PurchaseOrder:
        product = self.products[request.product_id]
        estimated_cost = (
            round(request.estimated_cost, 2)
            if request.estimated_cost is not None
            else round(request.quantity * product.unit_cost, 2)
        )
        order = PurchaseOrder(
            business_id=self.business.business_id,
            product_id=product.product_id,
            sku=product.sku,
            product_name=product.name,
            quantity=request.quantity,
            estimated_cost=estimated_cost,
            source_report_id=request.source_report_id,
            placed_by_type="user",
            placed_by_label="Demo user",
            note=request.note,
        )
        self.orders[order.order_id] = order
        return order

    def update_purchase_order_status(
        self,
        order_id: str,
        request: UpdatePurchaseOrderStatusRequest,
    ) -> PurchaseOrder:
        order = self.orders[order_id]
        previous_status = order.status
        order.status = request.status
        order.updated_at = utc_now()

        if previous_status != "arrived" and request.status == "arrived":
            self.add_inventory_movement(
                CreateInventoryMovementRequest(
                    product_id=order.product_id,
                    movement_type="purchase",
                    quantity=order.quantity,
                    note=f"Purchase order {order.order_id} received",
                )
            )

        self.orders[order.order_id] = order
        return order
def utc_now() -> datetime:
    return datetime.now(timezone.utc)

