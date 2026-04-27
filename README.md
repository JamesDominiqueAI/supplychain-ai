# SupplyChain AI

SupplyChain AI is a production-style inventory intelligence platform for small businesses that manage stock, suppliers, and purchase decisions with limited tooling.

The app helps owners and operators:

- track products, suppliers, inventory movements, and purchase orders
- identify low-stock and stockout risk
- generate cash-aware replenishment reports
- draft safe purchase orders
- compare supplier reliability and delivery exposure
- ask workspace-specific AI questions with guardrails
- audit AI decisions, fallback behavior, and token usage

## What Is Built

- Next.js workspace app with Clerk auth
- FastAPI backend with tenant-scoped APIs
- DynamoDB workspace persistence with local JSON fallback
- deterministic forecasting, inventory health, replenishment, supplier scorecards, anomalies, and cash logic
- guarded AI chat, morning brief, report comparison, scenario analysis, and multi-agent operations runs
- draft-first AI auto-orders and order notification events
- observability endpoint and deterministic evaluation script
- Terraform for DynamoDB, Lambda/API Gateway, S3/CloudFront, CloudWatch, and SNS
- static frontend deployment path and Lambda packaging script

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

- Operations Manager Agent: coordinates the specialist review.
- Inventory Risk Agent: finds critical SKUs and days-of-cover issues.
- Supplier Delay Agent: reviews late orders and supplier exposure.
- Cash Replenishment Agent: checks cash pressure and drafts orders only when automation is enabled.

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
UV_CACHE_DIR=/tmp/uv-cache uv run python backend/api/main.py
```

Run the frontend:

```bash
cd frontend
npm run dev
```

The frontend discovers local APIs on ports `8010`, `8011`, and `8012` unless `NEXT_PUBLIC_API_URL` is configured.

## Evaluation And Observability

Run deterministic evaluation scenarios:

```bash
python scripts/evaluate_project.py
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
