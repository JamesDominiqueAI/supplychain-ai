from __future__ import annotations

import importlib
import os
import unittest
from pathlib import Path
from datetime import timezone

from backend.tests.test_support import reset_fake_environment


class DynamoDBStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_fake_environment()
        self.store_module = importlib.import_module("dynamodb_store")
        importlib.reload(self.store_module)
        self.store_module.EmailAlertService.send_order_placed_alert = lambda *args, **kwargs: (True, "email sent")
        self.store_module.EmailAlertService.send_critical_stock_alert = lambda *args, **kwargs: (True, "critical sent")
        self.schemas = importlib.import_module("schemas")

    def test_workspace_state_persists_between_store_instances(self) -> None:
        store = self.store_module.DynamoDBStore(owner_user_id="owner-persist")
        initial_products = len(store.list_products())
        supplier = store.create_supplier(
            self.schemas.CreateSupplierRequest(name="Test Supplier", lead_time_days=4, reliability_score=0.95)
        )
        product = store.create_product(
            self.schemas.CreateProductRequest(
                sku="TEST-100",
                name="Test Product",
                category="Testing",
                current_stock=25,
                reorder_point=10,
                preferred_supplier_id=supplier.supplier_id,
                unit_cost=10,
            )
        )
        movement = store.add_inventory_movement(
            self.schemas.CreateInventoryMovementRequest(
                product_id=product.product_id,
                movement_type="sale",
                quantity=3,
                note="Persistence test sale",
            )
        )
        order = store.create_purchase_order(
            self.schemas.CreatePurchaseOrderRequest(
                product_id=product.product_id,
                supplier_id=supplier.supplier_id,
                quantity=5,
                note="Persistence test order",
            ),
            recipient_email="owner@example.com",
        )

        reloaded = self.store_module.DynamoDBStore(owner_user_id="owner-persist")

        self.assertEqual(len(reloaded.list_products()), initial_products + 1)
        self.assertTrue(any(item.sku == "TEST-100" for item in reloaded.list_products()))
        self.assertTrue(any(item.supplier_id == supplier.supplier_id for item in reloaded.list_suppliers()))
        self.assertTrue(any(item.movement_id == movement.movement_id for item in reloaded.list_inventory_movements()))
        self.assertTrue(any(item.order_id == order.order_id for item in reloaded.list_orders()))

    def test_receive_purchase_order_updates_stock_and_status(self) -> None:
        store = self.store_module.DynamoDBStore(owner_user_id="owner-receive")
        product = store.list_products()[0]
        starting_stock = product.current_stock
        order = store.create_purchase_order(
            self.schemas.CreatePurchaseOrderRequest(
                product_id=product.product_id,
                supplier_id=product.preferred_supplier_id,
                quantity=4,
                note="Receive test",
            ),
            recipient_email="owner@example.com",
        )

        updated = store.receive_purchase_order(
            order.order_id,
            self.schemas.ReceivePurchaseOrderRequest(quantity_received=2, note="Partial receipt"),
        )
        refreshed_product = next(item for item in store.list_products() if item.product_id == product.product_id)

        self.assertEqual(updated.status, "partially_received")
        self.assertEqual(updated.received_quantity, 2)
        self.assertEqual(refreshed_product.current_stock, starting_stock + 2)

    def test_report_and_business_settings_persist(self) -> None:
        store = self.store_module.DynamoDBStore(owner_user_id="owner-report")
        updated_business = store.update_business_settings(
            self.schemas.UpdateBusinessSettingsRequest(
                ai_enabled=False,
                notification_email="alerts@example.com",
                ai_automation_enabled=True,
            )
        )
        job = store.run_replenishment_job()

        reloaded = self.store_module.DynamoDBStore(owner_user_id="owner-report")

        self.assertFalse(updated_business.ai_enabled)
        self.assertEqual(reloaded.get_business().notification_email, "alerts@example.com")
        self.assertTrue(any(item.job_id == job.job_id for item in reloaded.list_jobs()))
        self.assertGreaterEqual(len(reloaded.list_reports()), 1)

    def test_corrupt_local_workspace_file_is_backed_up_and_recovered(self) -> None:
        store = self.store_module.DynamoDBStore(owner_user_id="owner-corrupt")
        corrupt_path = Path(store._local_state_path)
        corrupt_path.write_text("", encoding="utf-8")

        recovered = self.store_module.DynamoDBStore(owner_user_id="owner-corrupt")

        self.assertEqual(recovered._storage_mode, "file")
        self.assertEqual(recovered.get_business().name, "SupplyChain Workspace")
        backups = list(corrupt_path.parent.glob(f"{corrupt_path.name}.corrupt-*"))
        self.assertTrue(backups)

    def test_non_dev_defaults_prefer_dynamodb(self) -> None:
        os.environ["APP_ENV"] = "production"
        os.environ.pop("DYNAMODB_USE_REMOTE", None)
        os.environ.pop("DYNAMODB_USE_LOCAL", None)
        os.environ.pop("DYNAMODB_FALLBACK_TO_FILE", None)
        importlib.reload(self.store_module)

        store = self.store_module.DynamoDBStore(owner_user_id="owner-prod-default")

        self.assertEqual(store._storage_mode, "dynamodb")

    def test_timestamps_are_timezone_aware(self) -> None:
        store = self.store_module.DynamoDBStore(owner_user_id="owner-timezone")
        product = store.create_product(
            self.schemas.CreateProductRequest(
                sku="UTC-100",
                name="UTC Product",
                category="Testing",
                current_stock=10,
                reorder_point=5,
            )
        )
        order = store.create_purchase_order(
            self.schemas.CreatePurchaseOrderRequest(product_id=product.product_id, quantity=2),
            recipient_email="owner@example.com",
        )

        self.assertEqual(store.state.updated_at.tzinfo, timezone.utc)
        self.assertEqual(order.created_at.tzinfo, timezone.utc)
        self.assertEqual(order.updated_at.tzinfo, timezone.utc)

    def test_ai_auto_orders_default_to_drafts(self) -> None:
        store = self.store_module.DynamoDBStore(owner_user_id="owner-auto-draft")
        store.update_business_settings(
            self.schemas.UpdateBusinessSettingsRequest(ai_enabled=True, ai_automation_enabled=True)
        )

        result = store.auto_place_orders(recipient_email="owner@example.com")

        self.assertGreaterEqual(len(result.created_orders), 1)
        self.assertTrue(all(order.status == "draft" for order in result.created_orders))

    def test_failed_order_notifications_can_be_retried(self) -> None:
        store = self.store_module.DynamoDBStore(owner_user_id="owner-retry-email")
        store.email_alerts.send_order_placed_alert = lambda *args, **kwargs: (False, "temporary email outage")
        product = store.list_products()[0]
        order = store.create_purchase_order(
            self.schemas.CreatePurchaseOrderRequest(product_id=product.product_id, quantity=2),
            recipient_email="owner@example.com",
        )
        self.assertTrue(any(event.order_id == order.order_id and event.status == "failed" for event in store.list_order_notification_events()))

        store.email_alerts.send_order_placed_alert = lambda *args, **kwargs: (True, "email sent on retry")
        events = store.retry_failed_order_notifications(recipient_email="owner@example.com")

        self.assertTrue(any(event.order_id == order.order_id and event.status == "sent" for event in events))

    def test_ai_audit_logs_capture_token_usage(self) -> None:
        store = self.store_module.DynamoDBStore(owner_user_id="owner-ai-tokens")

        store._record_ai_audit(
            feature="chat",
            used_ai=True,
            status="accepted",
            input_preview="What should I buy?",
            output_preview="Prioritize critical stock.",
            confidence="high",
            input_tokens=12,
            output_tokens=8,
            total_tokens=20,
        )

        latest = store.list_ai_audit_logs()[0]
        self.assertEqual(latest.input_tokens, 12)
        self.assertEqual(latest.output_tokens, 8)
        self.assertEqual(latest.total_tokens, 20)


if __name__ == "__main__":
    unittest.main()
