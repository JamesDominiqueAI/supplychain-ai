# Architecture

SupplyChain AI is a tenant-scoped inventory intelligence app. The current implementation is a working product skeleton: a Clerk-protected Next.js workspace, a FastAPI backend, a DynamoDB-backed workspace document store with local JSON fallback, guarded AI workflows, order notifications, deterministic evaluation, and phased AWS infrastructure.

## Runtime Flow

```text
Operator
  -> Next.js workspace
  -> FastAPI API
  -> DynamoDB workspace item
       |-> products, suppliers, movements, orders
       |-> replenishment reports and jobs
       |-> agent runs and AI event logs
       |-> order notification events

FastAPI API
  |-> deterministic inventory, forecast, replenishment, supplier, and cash logic
  |-> optional LLM summaries, chat, scenarios, report comparisons, and agents
  |-> Resend/email notification adapter
  |-> in-process request metrics plus persisted AI event metrics

AWS deployment
  -> API Gateway HTTP API
  -> Lambda + Mangum
  -> DynamoDB
  -> S3 + CloudFront frontend
  -> CloudWatch dashboard, alarms, and SNS
```

## Major Components

### Frontend

The frontend is a Next.js Pages Router app with Clerk authentication and a workspace shell. Implemented screens are:

- `/dashboard`: business health, low-stock exposure, forecasts, anomalies, morning brief, latest report, agent controls, and chat.
- `/products`: product creation and catalog management.
- `/movements`: sale, purchase, and adjustment recording.
- `/orders`: manual and AI-drafted purchase orders, status updates, receiving flow, and notification visibility.
- `/reports`: replenishment jobs, report history, CSV export, cash scenarios, and report comparison.
- `/suppliers`: supplier catalog and scorecards.
- `/settings`: cash, AI, automation, notification, and critical-alert controls.

The API client discovers a local backend on ports `8010`, `8011`, or `8012` unless `NEXT_PUBLIC_API_URL` is set. Session-level caching keeps dashboards responsive without hiding recent writes for long.

### Backend API

The backend is FastAPI with Clerk JWT validation, local development fallback auth when configured, tenant scoping by actor id, CORS, request metrics, and Lambda compatibility through `backend/api/lambda_handler.py`.

Important endpoint groups:

- Workspace: `GET /api/business`, `PATCH /api/business/settings`, `GET /api/dashboard/summary`.
- Products and suppliers: `GET/POST /api/products`, `GET/POST /api/suppliers`, `GET /api/suppliers/scorecards`.
- Inventory: `GET /api/inventory/health`, `GET/POST /api/inventory/movements`.
- Replenishment and reports: `POST /api/analysis/replenishment`, `GET /api/jobs`, `GET /api/reports`, `GET /api/reports/{id}`, `GET /api/reports/{id}/export.csv`.
- Orders and notifications: `GET/POST /api/orders`, status and receiving endpoints, order notification listing/retry/test routes.
- AI: forecast, anomaly, brief, chat, scenario, comparison, auto-orders, agent catalog, agent runs, and specialist agent run endpoints.
- Observability: `GET /api/observability/metrics`.

### Data Layer

The active store is `DynamoDBStore`. In production it persists one workspace item per `owner_user_id` in DynamoDB. In local development and tests it can use a JSON file under `data/workspaces/` or a configured `LOCAL_STATE_PATH`.

The workspace state contains:

- business settings and cash
- products and suppliers
- inventory movements
- purchase orders
- replenishment jobs and reports
- agent runs
- AI event logs
- order notification events
- critical alert state

This document-store approach keeps the capstone deployable without a migration system, while still enforcing tenant isolation at the workspace boundary.

### Intelligence Layer

The system intentionally keeps arithmetic deterministic:

- current stock changes come from inventory movement and receiving logic
- risk levels come from stock, reorder points, demand, and lead time
- forecasts combine configured demand, movement history, and trend heuristics
- replenishment recommendations compute quantities, urgency, spend, and affordability before any LLM text is accepted

LLM calls are optional and guarded. They improve summaries, chat answers, morning briefs, cash scenarios, report comparisons, and multi-agent runs. If the model is disabled, unavailable, off-topic, low-confidence, or rejected by guardrails, the backend returns deterministic fallback output and records the event.

### Agents

The implemented agent team is exposed through direct API routes and can also run on an EventBridge schedule in Lambda:

- `operations_manager`: coordinates the run and summarizes the plan.
- `inventory_risk_agent`: identifies critical SKUs and stockout risk.
- `supplier_delay_agent`: reviews late orders and supplier exposure.
- `cash_replenishment_agent`: evaluates cash pressure and can draft orders only when automation is enabled.

Agents can use internal workspace state only. They do not call suppliers, negotiate, pay vendors, mutate stock directly, or place real external purchases.

## Deployment Shape

Terraform is split into phases:

- `1_foundation`: provider and shared project foundation.
- `2_database`: DynamoDB workspace table with encryption and point-in-time recovery.
- `3_agents`: reserved queue/agent phase retained for future async expansion.
- `4_frontend`: S3, CloudFront, optional Lambda API, API Gateway, CORS, and scheduled agent wiring.
- `5_enterprise`: SNS alerts, CloudWatch dashboard, CloudFront/API/Lambda alarms.

The `scripts/deploy_aws.sh` script packages the backend, applies Terraform, builds a static frontend with the deployed API URL, uploads assets, invalidates CloudFront, and applies monitoring.

## Current Trade-Offs

- Replenishment jobs run synchronously inside the API today; the Terraform agent phase leaves room for SQS/Lambda workers later.
- Request metrics are in-process and reset when the API worker restarts; AI metrics persist because they are summarized from internal AI events.
- The DynamoDB single-item workspace model is excellent for demo speed and tenant isolation, but a high-volume production system would eventually split hot entities into a more granular schema.
- External integrations are intentionally excluded: the product supports draft orders and email notifications, not real purchasing or supplier communication.

## Success Metrics

- fewer stockouts and urgent manual decisions
- lower dead inventory through better reorder timing
- clear supplier-delay visibility
- owner-facing recommendations with traceable numbers
- measurable AI fallback, refusal, and success rates
