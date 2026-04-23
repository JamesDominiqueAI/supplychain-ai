# SupplyChain AI

SupplyChain AI is a production-style AI platform for small businesses that manage inventory manually or through fragmented channels like WhatsApp, spreadsheets, and handwritten ledgers.

The system helps owners and operators:
- track inventory across one or more stores
- predict stockouts and restocking windows
- recommend purchase orders based on demand, lead time, and cash constraints
- summarize business health in plain language
- surface operational risks like supplier delay, low-stock exposure, and dead inventory

This project is intentionally designed with the same depth as Alex:
- frontend web app
- backend API
- async job workflows
- multi-agent analysis
- cloud deployment with Terraform
- monitoring and enterprise controls

## Why This Project

This project fits especially well if you care about:
- Haiti and similar markets where many businesses still operate informally
- supply chain and logistics problems
- building AI systems that are useful beyond demos
- showing both technical depth and market understanding

## Product Vision

Small businesses should not need ERP software or a data science team to answer:
- What am I running out of next week?
- What should I buy today with limited cash?
- Which products are moving too slowly?
- Which supplier is putting me at risk?
- What is the story of my business this month?

SupplyChain AI answers those questions with a mix of structured analytics and AI agents.

## Core User Types

- Owner: wants decisions, cash visibility, and plain-English summaries
- Store manager: wants low-stock alerts and replenishment guidance
- Purchasing lead: wants supplier comparisons and suggested orders
- Operations analyst: wants dashboards, exportable reports, and traceable logic

## Core AI Agents

- Demand Analyst: forecasts demand by SKU and location
- Replenishment Planner: recommends restocking actions
- Supplier Risk Analyst: flags delays, concentration risk, and unstable vendors
- Cash Flow Guard: checks whether recommended purchases fit budget constraints
- Operations Narrator: writes clear reports for owners and managers

## Suggested Stack

- Frontend: Next.js Pages Router
- Backend API: FastAPI
- Async jobs: SQS + Lambda
- Database: Aurora Serverless v2 PostgreSQL with Data API
- Auth: Clerk
- AI orchestration: OpenAI Agents SDK
- Vector / knowledge layer: S3 Vectors or pgvector depending on scope
- IaC: Terraform
- Monitoring: CloudWatch dashboards, alarms, structured logs

## Directory Structure

```text
supplychain-ai/
├── guides/
│   ├── 1_product_scope.md
│   ├── 2_data_model.md
│   ├── 3_backend_api.md
│   ├── 4_agents.md
│   ├── 5_frontend.md
│   ├── 6_cloud_deployment.md
│   ├── 7_enterprise.md
│   └── architecture.md
├── backend/
│   ├── api/
│   ├── planner/
│   ├── demand/
│   ├── replenishment/
│   ├── supplier_risk/
│   ├── narrator/
│   └── database/
├── frontend/
├── terraform/
│   ├── 1_foundation/
│   ├── 2_database/
│   ├── 3_agents/
│   ├── 4_frontend/
│   └── 5_enterprise/
└── scripts/
```

## MVP Scope

Build this first:
- authentication and tenant-aware data model
- products, suppliers, purchases, stock movements, and inventory balances
- low-stock dashboard
- forecast endpoint for top products
- replenishment recommendation job
- owner-facing report with cash-aware recommendations

Do not start with:
- advanced route optimization
- OCR for receipts
- offline mobile app
- marketplace integrations
- multi-country tax logic

## Best Starting Point

Start with [guides/1_product_scope.md](/home/ragive/projects/alex/supplychain-ai/guides/1_product_scope.md).

## Evaluation And Observability

The API exposes signed-in workspace metrics at `GET /api/observability/metrics`, including request latency, API error rate, AI success/fallback/refusal rates, and token usage summarized from AI audit logs.

Run the local deterministic evaluation scenarios with:

```bash
python scripts/evaluate_project.py
```

Run browser E2E tests after starting both servers and providing Clerk test credentials:

```bash
cd frontend
E2E_CLERK_EMAIL="your-test-user@example.com" E2E_CLERK_PASSWORD="..." npm run test:e2e
```

See [guides/8_ai_observability_evaluation.md](guides/8_ai_observability_evaluation.md) for the LLM prompts, structured outputs, guardrails, trade-offs, and expected evaluation scenarios.

For AWS deployment, use:

```bash
bash scripts/deploy_aws.sh
```

The deploy script will automatically import an existing DynamoDB workspace table into Terraform state
if the table already exists in AWS but is missing from the local Terraform state.

If AWS blocks the deployment because of IAM permissions, see [guides/9_aws_deployment_runbook.md](guides/9_aws_deployment_runbook.md).

## CI/CD

GitHub Actions runs backend tests, deterministic AI evaluation scenarios, and the frontend build on pull requests and pushes to `main`.
Pushes to `main` deploy to AWS after CI passes. Manual workflow runs can redeploy any branch, tag, or commit SHA; use that same `git_ref` input to roll back by redeploying an older known-good commit.

Required GitHub secrets:

```text
AWS_ROLE_ARN
DEFAULT_AWS_REGION
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
CLERK_SECRET_KEY
CLERK_JWKS_URL
CLERK_ISSUER
OPENAI_API_KEY
RESEND_API_KEY
RESEND_FROM_EMAIL
```

Optional secrets:

```text
ALARM_EMAIL
DYNAMODB_TABLE_NAME
OPENAI_MODEL
```
