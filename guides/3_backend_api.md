# Guide 3: Backend API

The backend is a FastAPI service that exposes the workspace contract used by the Next.js frontend and by Lambda deployment. It owns auth, tenant scoping, deterministic business logic, guarded AI features, email notification adapters, and observability.

## Local Runtime

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --package supplychain-api python backend/api/main.py
```

The API defaults to `127.0.0.1:8010`. In development it prefers the local JSON workspace store unless `DYNAMODB_USE_REMOTE=true` is set.

## Core Endpoints

### Health and auth

- `GET /health`
- `GET /api/auth/debug`

### Workspace and dashboard

- `GET /api/business`
- `PATCH /api/business/settings`
- `GET /api/dashboard/summary`

### Catalog and inventory

- `GET /api/products`
- `POST /api/products`
- `GET /api/suppliers`
- `POST /api/suppliers`
- `GET /api/suppliers/scorecards`
- `GET /api/inventory/health`
- `GET /api/inventory/movements`
- `POST /api/inventory/movements`

### Replenishment, jobs, and reports

- `POST /api/analysis/replenishment`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/reports`
- `GET /api/reports/{report_id}`
- `GET /api/reports/{report_id}/export.csv`

### Orders and notifications

- `GET /api/orders`
- `POST /api/orders`
- `POST /api/orders/{order_id}/status`
- `POST /api/orders/{order_id}/receive`
- `GET /api/notifications/orders`
- `POST /api/notifications/orders/retry`
- `POST /api/notifications/test-order-email`

### AI and agents

- `GET /api/ai/forecast`
- `GET /api/ai/anomalies`
- `GET /api/ai/brief`
- `POST /api/ai/chat`
- `POST /api/ai/scenario`
- `GET /api/ai/report-comparison`
- `POST /api/ai/auto-orders`
- `GET /api/ai/agents`
- `GET /api/ai/agents/runs`
- `POST /api/ai/agents/operations`
- `POST /api/ai/agents/inventory-risk`
- `POST /api/ai/agents/supplier-delay`
- `POST /api/ai/agents/cash-replenishment`

### Observability

- `GET /api/observability/metrics`

## Implementation Responsibilities

- Validate Clerk bearer tokens and derive the workspace owner.
- Scope every store operation to the actor workspace.
- Maintain deterministic inventory, replenishment, supplier scorecard, and forecast logic.
- Reject off-topic or unsafe chat prompts.
- Convert AI failures into deterministic fallback responses.
- Record internal AI events and request metrics.
- Package cleanly for Lambda with `Mangum`.

## Current Workflow Model

Replenishment and agent workflows currently run inline and complete quickly enough for the MVP. They still create persisted job, report, event, and agent-run records so the product behaves like an operational system. The `terraform/3_agents` phase remains the expansion point for SQS-backed workers when the project needs true async execution.

## Guardrails

- Tenant scope is backend-derived, not client-provided.
- Stock changes go through inventory movements or purchase-order receiving.
- AI cannot claim external supplier calls, negotiations, payments, or account access.
- AI order automation is constrained by `ai_enabled`, `ai_automation_enabled`, cash, and `AI_AUTO_ORDER_MAX_SPEND`.
- Structured AI output is validated; rejected output falls back to deterministic text.
- Every AI decision path writes an internal event used by observability metrics.
