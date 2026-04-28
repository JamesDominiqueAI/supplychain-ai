# SupplyChain AI

SupplyChain AI is a cloud-ready inventory intelligence workspace for small businesses that need sharper purchasing decisions without buying a full ERP system.

It turns everyday inventory records into an operations cockpit: stock movements become risk signals, supplier delays become visible, replenishment plans become cash-aware, and AI agents explain what needs attention before the business runs out of critical materials.

The core idea is simple: deterministic business logic remains the source of truth, while guarded AI helps the owner understand risk, compare options, and draft safe next steps.

The app helps teams:

- track products, suppliers, inventory movements, and purchase orders
- identify low-stock, days-of-cover, and stockout risk
- generate cash-aware replenishment reports
- draft safe purchase orders without bypassing user control
- compare supplier reliability and delivery exposure
- ask workspace-specific AI questions with guardrails
- run a separated agent team for daily operations review
- audit AI decisions, fallback behavior, token usage, and agent runs

## What Is Built

- Next.js workspace app with Clerk auth
- FastAPI backend with tenant-scoped APIs
- DynamoDB workspace persistence with local JSON fallback
- deterministic forecasting, inventory health, replenishment, supplier scorecards, anomalies, and cash logic
- guarded AI chat, morning brief, report comparison, scenario analysis, and separated multi-agent operations runs
- draft-first AI auto-orders and order notification events
- observability endpoint and deterministic evaluation script
- Terraform for DynamoDB, Lambda/API Gateway, S3/CloudFront, CloudWatch, and SNS
- static frontend deployment path and Lambda packaging script

## Why It Matters

Many small stores know what they sold yesterday but not what they will run out of tomorrow. SupplyChain AI bridges that gap by combining operational records with forecasting, cash limits, supplier behavior, and explainable AI.

Instead of saying only “buy more,” the system answers:

- Which SKU is most urgent?
- How many days of cover are left?
- Which orders are late?
- Can the business afford the full replenishment plan?
- Which recommendations should become draft purchase orders?
- Why did the AI accept, refuse, or fall back?

## Product Vision

Small businesses should not need a full ERP system or a data science team to answer:

- What am I running out of next week?
- What should I buy today with limited cash?
- Which products are moving too slowly?
- Which supplier is putting me at risk?
- What is the story of my business this month?

SupplyChain AI answers those questions with deterministic operations logic first, then optional AI explanations and agent reviews.

## Core User Types

- Owner: wants decisions, cash visibility, and plain-English summaries.
- Store manager: records movements, receives orders, and watches stock risk.
- Purchasing lead: reviews recommended orders and supplier reliability.
- Operations analyst: uses reports, exports, audit logs, and observability signals.

## Core AI Agents

The agent team is separated in `backend/database/src/agents.py`:

- Operations Manager Agent: coordinates the specialist review and summarizes the run.
- Inventory Risk Agent: finds critical SKUs, low days of cover, and stockout exposure.
- Supplier Delay Agent: reviews late orders and supplier delivery risk.
- Cash Replenishment Agent: checks cash pressure and drafts orders only when automation is enabled.

Agent guardrails:

- internal workspace tools only
- no external supplier calls
- no negotiation claims
- no payments or off-platform purchases
- draft-first order behavior by default
- every run persisted and summarized in the AI audit trail

## Stack

- Frontend: Next.js Pages Router, React, TypeScript, Clerk
- Backend API: FastAPI, Pydantic, Mangum
- Storage: DynamoDB in production, local JSON fallback in development/test
- AI: OpenAI-compatible provider calls with deterministic fallback paths
- Notifications: Resend-compatible email adapter and persisted notification events
- Infrastructure: Terraform, Lambda, API Gateway, S3, CloudFront, CloudWatch, SNS

## Directory Structure

```text
supplychain-ai/
├── guides/
├── backend/
│   ├── api/
│   ├── database/
│   ├── planner/
│   ├── demand/
│   ├── replenishment/
│   ├── supplier_risk/
│   └── narrator/
├── frontend/
├── terraform/
│   ├── 1_foundation/
│   ├── 2_database/
│   ├── 3_agents/
│   ├── 4_frontend/
│   └── 5_enterprise/
├── scripts/
└── PROJECT_PRESENTATION.md
```

## Local Development

Run the backend:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --package supplychain-api python backend/api/main.py
```

Run the frontend:

```bash
cd frontend
npm run dev
```

The frontend discovers local APIs on ports `8010`, `8011`, and `8012` unless `NEXT_PUBLIC_API_URL` is configured.

## Docker

Run the full app with Docker Compose:

```bash
docker compose up --build
```

Then open `http://localhost:3000`. The backend is available at `http://localhost:8010`.

Docker defaults to local JSON workspace storage and persists it in the `backend-workspaces` volume. A local `.env` file is optional; when present, Compose passes server-side values into the backend and passes only public `NEXT_PUBLIC_*` values into the frontend. For the authenticated workspace experience, set Clerk values such as `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `CLERK_ISSUER`, and `CLERK_JWKS_URL`.

Useful commands:

```bash
docker compose down
docker compose down --volumes
docker compose logs -f backend
docker compose logs -f frontend
```

## Evaluation And Observability

Run deterministic evaluation scenarios:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --package supplychain-api python scripts/evaluate_project.py
```

The evaluation checks seed data, critical stock behavior, replenishment reporting, draft-first auto-orders, chat guardrails, AI audit persistence, multi-agent persistence, and tenant isolation.

The API exposes signed-in workspace metrics at:

```text
GET /api/observability/metrics
```

See [guides/8_ai_observability_evaluation.md](guides/8_ai_observability_evaluation.md) for guardrails, metrics, and evaluation details.

## Frontend Build And E2E

```bash
cd frontend
npm run build
```

Browser E2E requires both servers and Clerk test credentials:

```bash
cd frontend
E2E_CLERK_EMAIL="your-test-user@example.com" E2E_CLERK_PASSWORD="..." npm run test:e2e
```

## AWS Deployment

```bash
bash scripts/deploy_aws.sh
```

The deployment script packages the backend, applies Terraform, builds the frontend with the deployed API URL, uploads static assets to S3, invalidates CloudFront, and applies monitoring.

If AWS blocks deployment because of IAM permissions, see [guides/9_aws_deployment_runbook.md](guides/9_aws_deployment_runbook.md).

## Presentation

Use [PROJECT_PRESENTATION.md](PROJECT_PRESENTATION.md) for a project walkthrough, architecture summary, AI design, evaluation story, current limitations, and next steps.
