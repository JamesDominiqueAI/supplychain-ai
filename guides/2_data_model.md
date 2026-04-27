# Guide 2: Data Model

The implemented data model is a tenant-scoped workspace document. Each signed-in actor receives an isolated workspace keyed by `owner_user_id`. Production storage uses DynamoDB; local development and deterministic tests can use a JSON file with the same Pydantic schemas.

## Workspace Boundary

Every workspace contains exactly one business context plus operational records:

- `business`
- `products`
- `suppliers`
- `movements`
- `orders`
- `jobs`
- `reports`
- `agent_runs`
- `ai_audit_logs`
- `order_notification_events`
- `critical_alert_state`

The API never accepts a client-provided tenant id. Tenant scope is derived from the Clerk session actor, or from the local development fallback actor when explicitly enabled.

## Core Entities

### Business

- `business_id`
- `name`
- `country`
- `currency`
- `available_cash`
- `ai_enabled`
- `ai_automation_enabled`
- `notification_email`
- `critical_alerts_enabled`
- `created_at`

### Product

- `product_id`
- `business_id`
- `sku`
- `name`
- `category`
- `unit`
- `reorder_point`
- `target_days_of_cover`
- `lead_time_days`
- `current_stock`
- `avg_daily_demand`
- `unit_cost`
- `preferred_supplier_id`
- `created_at`

### Supplier

- `supplier_id`
- `business_id`
- `name`
- `contact_phone`
- `lead_time_days`
- `reliability_score`
- `notes`
- `created_at`

### Inventory Movement

- `movement_id`
- `business_id`
- `product_id`
- `movement_type`: `sale`, `purchase`, or `adjustment`
- `quantity`
- `occurred_at`
- `note`

Movements are the audit trail for stock changes. Sales reduce stock, purchases and positive adjustments increase it, and validation prevents non-positive movement quantities.

### Purchase Order

- `order_id`
- `business_id`
- `product_id`
- `sku`
- `product_name`
- `quantity`
- `estimated_cost`
- `status`
- `supplier_id`
- `supplier_name`
- `expected_delivery_date`
- `received_quantity`
- `last_received_at`
- `is_late`
- `days_late`
- `source_report_id`
- `placed_by_type`: `user`, `llm`, or `system`
- `placed_by_label`
- `note`
- timestamps

Receiving an order records received quantity and updates inventory through controlled backend logic.

### Replenishment Report

- `report_id`
- `business_id`
- `summary`
- `total_recommended_spend`
- `affordable_now`
- `actions`
- `recommendations`
- `generated_at`

Each recommendation includes SKU, current stock, reorder point, forecast demand, days of cover, EOQ-style quantity, recommended quantity, estimated cost, urgency, recommendation type, confidence, and rationale.

### AI Audit Log

AI and fallback behavior is recorded with:

- feature name
- status: accepted, fallback, or refused
- whether AI was used
- confidence
- reason/refusal text
- short preview fields
- token usage when available
- created timestamp

This gives the project a real trail for AI behavior without storing full prompts and responses.

## Derived Views

Several important objects are derived rather than manually stored as separate truth:

- inventory health: computed from product stock, reorder point, demand, and lead time
- supplier scorecards: computed from supplier settings and purchase-order history
- forecast insights: computed from baseline demand, recent sales, and trend direction
- anomaly insights: computed from stock, sales, supplier delay, and cash pressure
- observability metrics: request metrics in memory plus persisted AI audit summaries

## Validation Rules

- SKU is normalized to uppercase and must be unique within a workspace.
- Product name, category, unit, and supplier name cannot be blank.
- Movement and order quantities must be positive.
- Received quantity cannot be negative and cannot exceed intended order handling constraints.
- Notification email must look like a valid email address.
- AI output cannot directly mutate stock, cash, supplier state, or order status.
- AI-created orders are draft-first unless automation settings explicitly allow more.
