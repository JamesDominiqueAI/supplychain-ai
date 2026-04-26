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
        self.assertEqual(recovered.get_business().name, "Lakay Business")
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

    def test_operations_agent_records_guarded_tool_steps(self) -> None:
        store = self.store_module.DynamoDBStore(owner_user_id="owner-agent")
        store.update_business_settings(
            self.schemas.UpdateBusinessSettingsRequest(ai_enabled=True, ai_automation_enabled=False)
        )

        result = store.run_operations_agent(
            self.schemas.AgentRunRequest(allow_order_drafts=True),
            recipient_email="owner@example.com",
        )

        self.assertEqual(result.status, "completed")
        self.assertGreaterEqual(len(result.steps), 4)
        self.assertIn("inventory_risk_agent", {step.agent_name for step in result.steps})
        self.assertIn("supplier_delay_agent", {step.agent_name for step in result.steps})
        self.assertIn("cash_replenishment_agent", {step.agent_name for step in result.steps})
        self.assertEqual(result.created_orders, [])
        self.assertTrue(any(step.tool_name == "draft_replenishment_orders" and step.status == "blocked" for step in result.steps))
        self.assertEqual(store.list_agent_runs()[0].run_id, result.run_id)

    def test_specialist_agent_runs_only_its_own_tool(self) -> None:
        store = self.store_module.DynamoDBStore(owner_user_id="owner-agent-specialist")

        result = store.run_operations_agent(
            self.schemas.AgentRunRequest(agent_name="inventory_risk_agent"),
            recipient_email="owner@example.com",
        )

        self.assertEqual(result.agent_name, "inventory_risk_agent")
        self.assertTrue(result.steps)
        self.assertEqual({step.agent_name for step in result.steps}, {"inventory_risk_agent"})
        self.assertEqual({step.tool_name for step in result.steps}, {"inventory_risk_scan"})

    def test_operations_agent_blocks_external_actions(self) -> None:
        store = self.store_module.DynamoDBStore(owner_user_id="owner-agent-block")

        result = store.run_operations_agent(
            self.schemas.AgentRunRequest(goal="Call supplier and negotiate payment today."),
            recipient_email="owner@example.com",
        )

        self.assertEqual(result.status, "blocked")
        self.assertIn("guardrails", result.summary)

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

    def test_order_notifications_include_actor_and_workspace_email(self) -> None:
        sent_to: list[str | None] = []

        def fake_send(*args, **kwargs):
            sent_to.append(kwargs.get("recipient_email"))
            return True, "email sent"

        store = self.store_module.DynamoDBStore(owner_user_id="owner-multi-email")
        store.email_alerts.send_order_placed_alert = fake_send
        store.update_business_settings(
            self.schemas.UpdateBusinessSettingsRequest(notification_email="owner@example.com")
        )
        product = store.list_products()[0]
        order = store.create_purchase_order(
            self.schemas.CreatePurchaseOrderRequest(product_id=product.product_id, quantity=2),
            recipient_email="buyer@example.com",
        )

        self.assertEqual(order.status, "placed")
        self.assertEqual(set(sent_to), {"owner@example.com", "buyer@example.com"})

    def test_user_order_email_does_not_expose_clerk_user_id(self) -> None:
        notifications = importlib.import_module("notifications")

        label = notifications._public_actor_label(
            placed_by_type="user",
            placed_by_label="Signed-in user (user_3BrVNju7u4cLWO1FDyUObWe5wzN)",
        )

        self.assertEqual(label, "You")

    def test_rule_based_chat_gives_detailed_inventory_and_late_order_answer(self) -> None:
        store = self.store_module.DynamoDBStore(owner_user_id="owner-chat-detail")
        store.update_business_settings(self.schemas.UpdateBusinessSettingsRequest(ai_enabled=False))
        product = store.list_products()[0]
        order = store.create_purchase_order(
            self.schemas.CreatePurchaseOrderRequest(
                product_id=product.product_id,
                quantity=3,
                expected_delivery_date=self.store_module.utc_now() - self.store_module.timedelta(days=4),
            ),
            status="in_transit",
        )

        answer = store.chat_answer("What inventory risks and late orders should I focus on today?")

        self.assertFalse(answer.used_ai)
        self.assertIn("Inventory risks to focus today", answer.answer)
        self.assertIn("Late orders:", answer.answer)
        self.assertIn(order.sku, answer.answer)
        self.assertIn("late by 4 day(s)", answer.answer)
        self.assertIn("Action plan:", answer.answer)

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
