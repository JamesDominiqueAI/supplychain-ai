# SupplyChain AI Project Presentation

## 1. Project Summary

SupplyChain AI is an AI-assisted inventory operations platform for small businesses that manage products, supplier relationships, stock movements, and purchase decisions without a full ERP system. It behaves like a lightweight stock room command center: records come in, risk is calculated, agents review the workspace, and the owner sees practical next steps.

The product helps an owner answer practical daily questions:

- Which products are likely to stock out?
- What should I reorder now?
- How much cash will the recommended orders require?
- Which supplier is creating delivery risk?
- What changed since the last replenishment report?
- Can the system explain the recommendation in plain language?

The current repository is more than a concept. It includes a working frontend, backend API, local and cloud storage strategy, AI guardrails, deterministic evaluation scenarios, browser workflow tests, AWS infrastructure, deployment scripts, and operational documentation.

For live demos, run `scripts/seed_demo.py --reset` to create a predictable workspace with products, suppliers, movements, a replenishment report, an operations-agent run, and an off-topic refusal that appears in `/audit`.

## 2. Target Users

- Owner: wants clear decisions, cash awareness, and plain-language summaries.
- Store manager: records sales, purchases, adjustments, and receives orders.
- Purchasing lead: reviews supplier risk and creates purchase orders.
- Operator/analyst: checks reports, audits AI behavior, and compares replenishment plans.

## 3. Product Experience

The app opens into an authenticated workspace rather than a marketing page. The core screens are:

- Dashboard: operational status, low stock, forecasts, anomalies, morning brief, latest report, AI chat, and an automatically running agent-team review.
- Products: SKU catalog with demand, lead time, stock, reorder point, cost, and supplier preference.
- Movements: sale, purchase, and adjustment recording.
- Orders: purchase-order creation, AI-drafted orders, receiving flow, late-order visibility, and notification history.
- Reports: replenishment generation, CSV export, cash scenarios, report comparison, and AI audit.
- Suppliers: supplier records and scorecards.
- Settings: available cash, AI enablement, automation, notification email, and critical-stock alerts.

## 4. Technical Architecture

Frontend:

- Next.js Pages Router
- React and TypeScript
- Clerk authentication
- typed API layer with token handling, retry, short-lived cache, and local API discovery
- static export path for S3 and CloudFront

Backend:

- FastAPI
- Clerk JWT validation
- tenant scoping by actor id
- DynamoDB-backed workspace store
- local JSON fallback for development and tests
- deterministic inventory, forecast, replenishment, supplier, cash, and anomaly logic
- optional LLM summaries and chat with guardrails
- Resend-compatible notification service
- Lambda support through Mangum

Cloud:

- DynamoDB table
- Lambda API
- API Gateway HTTP API
- S3 frontend bucket
- CloudFront CDN
- optional EventBridge scheduled agent
- CloudWatch dashboard and alarms
- SNS alert topic

Architecture tradeoffs:

- The single-document workspace model is simple and demo-friendly, but it should migrate before production-scale event history because DynamoDB items are limited to roughly 400 KB.
- The production migration path is a multi-item DynamoDB model using `PK=WORKSPACE#{owner_user_id}` and typed `SK` values for products, movements, orders, reports, and AI audit events.
- Replenishment and agent runs execute inline today, while `backend/api/worker_handler.py` demonstrates the SQS worker handoff pattern for production hardening.
- Chat uses the current structured workspace snapshot today; a RAG layer over historical reports, supplier events, and audit summaries is the natural next step.

## 5. AI Design

The strongest design choice is that AI is not the system of record.

Deterministic code owns:

- stock balance
- movement validation
- purchase-order status
- forecast inputs
- replenishment quantities
- estimated spend
- risk levels
- supplier scorecards

AI improves:

- owner-facing summaries
- recommendation explanations
- workspace chat
- morning briefs
- cash scenario explanations
- report comparisons
- multi-agent operations reviews

The backend records accepted, fallback, and refused AI paths in an audit log. The frontend exposes this in `/audit`, where an interviewer can inspect status, feature, reason/refusal text, input and output previews, confidence, token usage, refusal rate, fallback rate, and feature counts.

Concrete demo example:

1. Ask the workspace chat an off-topic prompt such as “Write a poem about the weather.”
2. The backend refuses it because the assistant only handles operations topics.
3. `/audit` shows the event as `refused`, records that AI was not used, displays the input preview, and shows the refusal reason.

Safety hardening note: current guardrails cover topic boundaries and unsupported external actions. A next hardening layer should add explicit prompt-injection and policy-bypass tests, for example prompts that ask the assistant to ignore inventory rules, reveal hidden system instructions, or claim supplier contact anyway.

## 6. Agent Team

Implemented agents:

- Operations Manager Agent: coordinates the specialist review.
- Inventory Risk Agent: identifies critical SKUs and days-of-cover risk.
- Supplier Delay Agent: reviews late orders and delivery exposure.
- Cash Replenishment Agent: evaluates cash pressure and drafts orders only when automation is enabled.

Implementation boundary:

- agent orchestration lives in `backend/database/src/agents.py`
- workspace persistence and audit history stay in `dynamodb_store.py`
- specialists return structured step records
- state-changing actions still pass through guarded store methods

Safety boundaries:

- agents use internal workspace data only
- no external supplier calls
- no negotiations
- no payments
- no real off-platform purchases
- draft-first order behavior by default
- scheduled runs disabled unless explicitly configured

## 7. Data Model

The project uses a workspace document model keyed by `owner_user_id`. Each workspace stores:

- business settings
- products
- suppliers
- inventory movements
- purchase orders
- replenishment jobs
- reports
- agent runs
- AI audit logs
- order notification events
- critical alert state

This keeps deployment simple and makes tenant isolation clear. For a larger production version, high-volume objects could be split into separate DynamoDB item types or relational tables.

## 8. Evaluation Results

The deterministic evaluation script checks the project as a product, not only as isolated functions. It validates:

- seed data exists
- sales can push an item into critical stock risk
- replenishment produces a completed job and recommendations
- AI automation creates draft orders by default
- off-topic chat is refused
- AI decisions are logged
- multi-agent runs persist specialist outputs
- tenant isolation prevents cross-owner visibility

Run it with:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --package supplychain-api python scripts/evaluate_project.py
```

Example metrics to show during a review:

- AI success/fallback/refusal rates from `/api/observability/metrics`.
- p95 API latency from the in-process request metrics.
- token totals from AI audit events.
- feature counts showing which AI surfaces are active.

## 9. What Makes It Feel Real

- Authenticated workspace instead of a static demo.
- User-facing workflows for catalog, movements, orders, reports, suppliers, and settings.
- Dedicated `/audit` page for accepted, fallback, and refused AI decisions.
- Actual purchase-order lifecycle, including receiving and late-order state.
- Cash-aware replenishment instead of generic recommendations.
- Supplier scorecards connected to order history.
- Guarded AI with refusal and fallback behavior.
- Audit logs and observability endpoint.
- AWS infrastructure and deploy scripts.
- Docker Compose local runtime.
- Deterministic evaluation and E2E workflow tests.
- Documentation now describes the implemented system rather than only future ideas.

## 10. Current Limitations

- Async queue workers are planned but not active; workflows currently run inline through the API.
- Request metrics are in-process and should eventually be shipped to durable monitoring.
- Role-based permissions are not implemented yet.
- External integrations such as POS, WhatsApp, invoice OCR, and supplier portals are intentionally out of scope.
- The single-document workspace model is excellent for capstone/demo deployment, but high-volume production usage would require a more granular storage design.
- Git history is functional, but a stronger team-engineering story would use issues, branches, pull requests, and review notes.

## 11. Recommended Next Steps

1. Add durable request metrics through CloudWatch custom metrics or an observability platform.
2. Convert replenishment and agent jobs to an SQS-backed worker path.
3. Add role-based permissions for owner, manager, and purchasing roles.
4. Add a retrieval layer for workspace chat using embeddings over past reports, supplier history, and order events.
5. Migrate large workspaces from the single-document model to a DynamoDB multi-item model with keys such as `PK=WORKSPACE#{owner_user_id}` and `SK=ENTITY#{type}#{id}` plus GSIs for entity type, created date, and supplier/product lookups.
6. Add CSV import for products and movements.
7. Expand E2E coverage for settings, report comparison, supplier scorecards, and the audit page.
8. Add a demo data reset command for presentations.
9. Use self-authored pull requests with descriptions to show code review discipline.

The detailed hardening roadmap lives in `guides/10_capstone_hardening.md`.
