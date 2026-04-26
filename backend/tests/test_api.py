from __future__ import annotations

import asyncio
import importlib
import unittest

from backend.tests.test_support import reset_fake_environment


class FakeApiStore:
    def __init__(self) -> None:
        self.owner_user_id = "api-test-user"
        self.products = []
        self.orders = []

    def get_business(self):
        return {"business_id": "biz-1", "name": "SupplyChain Workspace"}

    def list_products(self):
        return self.products

    def create_product(self, payload):
        product = {
            "product_id": f"product-{len(self.products) + 1}",
            "business_id": "biz-1",
            "sku": payload.sku,
            "name": payload.name,
            "category": payload.category,
            "unit": payload.unit,
            "reorder_point": payload.reorder_point,
            "target_days_of_cover": payload.target_days_of_cover,
            "lead_time_days": payload.lead_time_days,
            "current_stock": payload.current_stock,
            "avg_daily_demand": payload.avg_daily_demand,
            "unit_cost": payload.unit_cost,
            "preferred_supplier_id": payload.preferred_supplier_id,
            "created_at": "2026-04-20T00:00:00",
        }
        self.products.append(product)
        return product

    def list_orders(self):
        return self.orders

    def create_purchase_order(self, payload, **kwargs):
        product = next(item for item in self.products if item["product_id"] == payload.product_id)
        order = {
            "order_id": f"order-{len(self.orders) + 1}",
            "business_id": "biz-1",
            "product_id": product["product_id"],
            "sku": product["sku"],
            "product_name": product["name"],
            "quantity": payload.quantity,
            "estimated_cost": product["unit_cost"] * payload.quantity,
            "status": "placed",
            "supplier_id": payload.supplier_id,
            "supplier_name": None,
            "expected_delivery_date": None,
            "received_quantity": 0,
            "last_received_at": None,
            "is_late": False,
            "days_late": 0,
            "source_report_id": payload.source_report_id,
            "placed_by_type": kwargs.get("placed_by_type", "user"),
            "placed_by_label": kwargs.get("placed_by_label"),
            "note": payload.note,
            "created_at": "2026-04-20T00:00:00",
            "updated_at": "2026-04-20T00:00:00",
        }
        self.orders.append(order)
        return order

    def update_purchase_order_status(self, order_id, payload, **kwargs):
        order = next(item for item in self.orders if item["order_id"] == order_id)
        order["status"] = payload.status
        order["last_recipient_email"] = kwargs.get("recipient_email")
        return order


class ApiFunctionTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_fake_environment()
        self.api_main = importlib.import_module("main")
        self.schemas = importlib.import_module("schemas")
        self.fake_store = FakeApiStore()

    def test_business_and_product_flow(self) -> None:
        business = asyncio.run(self.api_main.get_business(self.fake_store))
        self.assertEqual(business["name"], "SupplyChain Workspace")

        created = asyncio.run(
            self.api_main.create_product(
                self.schemas.CreateProductRequest(
                    sku="API-200",
                    name="API Product",
                    category="API Tests",
                    current_stock=15,
                    reorder_point=8,
                    lead_time_days=3,
                    unit_cost=22,
                ),
                self.fake_store,
            )
        )
        self.assertEqual(created["sku"], "API-200")

        listed = asyncio.run(self.api_main.list_products(self.fake_store))
        self.assertTrue(any(item["sku"] == "API-200" for item in listed))

    def test_order_flow_returns_created_order(self) -> None:
        created_product = asyncio.run(
            self.api_main.create_product(
                self.schemas.CreateProductRequest(
                    sku="API-201",
                    name="API Order Product",
                    category="API Tests",
                    current_stock=15,
                    reorder_point=8,
                    lead_time_days=3,
                    unit_cost=22,
                ),
                self.fake_store,
            )
        )

        created_order = asyncio.run(
            self.api_main.create_order(
                self.schemas.CreatePurchaseOrderRequest(
                    product_id=created_product["product_id"],
                    supplier_id=created_product.get("preferred_supplier_id"),
                    quantity=6,
                    note="API order test",
                ),
                self.fake_store,
                actor_email="owner@example.com",
            )
        )

        self.assertEqual(created_order["sku"], "API-201")
        self.assertEqual(created_order["status"], "placed")

        orders = asyncio.run(self.api_main.list_orders(self.fake_store))
        self.assertTrue(any(item["order_id"] == created_order["order_id"] for item in orders))

    def test_status_update_passes_actor_email_to_store(self) -> None:
        self.fake_store.orders.append({"order_id": "order-1", "status": "approved"})

        updated = asyncio.run(
            self.api_main.update_order_status(
                "order-1",
                self.schemas.UpdatePurchaseOrderStatusRequest(status="placed"),
                self.fake_store,
                actor_email="buyer@example.com",
            )
        )

        self.assertEqual(updated["status"], "placed")
        self.assertEqual(updated["last_recipient_email"], "buyer@example.com")


if __name__ == "__main__":
    unittest.main()
