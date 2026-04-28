# Guide 10: Capstone Hardening Plan

This guide turns the main reviewer concerns into an explicit engineering roadmap. It is intentionally practical: each section names the current state, why it matters, and the next implementation step.

## 1. AI Audit Visibility

Current state:

- The backend persists AI audit events for chat, reports, briefs, scenarios, comparisons, and agents.
- The `/audit` page exposes accepted, fallback, and refused events with status, feature, reason/refusal text, input and output previews, confidence, token usage, refusal rate, fallback rate, and feature counts.

Interview demo:

1. Ask the workspace chat an off-topic prompt such as `Write a poem about the weather`.
2. The backend refuses it because the assistant is limited to inventory, suppliers, orders, cash, reports, forecasts, and related operations.
3. Open `/audit` and show the refused event, input preview, fallback/AI-used flag, confidence, and refusal reason.

Next hardening step:

- Add a screenshot to the README or presentation after running the demo workspace.

## 2. Async Worker Path

Current state:

- Replenishment jobs and agent runs execute inline in the API.
- The API still persists job records, report records, agent runs, and audit logs, so the user experience behaves like a job-based workflow.
- Terraform has a reserved `3_agents` phase for queues and worker infrastructure.

Why this matters:

- Logistics workloads can spike. If many workspaces trigger replenishment reports or agent reviews at once, inline execution ties up API workers and can degrade request latency.

Target design:

```text
API
  -> create analysis job with status=pending
  -> send SQS message {owner_user_id, job_id, job_type}
  -> return job_id immediately

Worker Lambda
  -> receive SQS message
  -> load workspace
  -> run replenishment or agent workflow
  -> persist report/agent run/audit logs
  -> mark job completed or failed

Frontend
  -> poll /api/jobs/{job_id}
  -> refresh reports or agent runs when complete
```

Minimal implementation:

- Add an environment flag such as `ASYNC_JOBS_ENABLED=true`.
- When enabled, `POST /api/analysis/replenishment` writes a pending job and publishes to SQS.
- Keep the current inline path as the local fallback.
- Add a worker entrypoint that can process the same job payload locally or in Lambda.

## 3. Role-Based Permissions

Current state:

- Clerk authenticates users and the backend scopes data by actor id.
- The app has clear personas, but authorization is workspace-level rather than role-level.

Why this matters:

- Owner, manager, and purchasing lead personas should not have identical powers.

Recommended role matrix:

| Capability | Owner | Manager | Purchasing Lead | Analyst |
| --- | --- | --- | --- | --- |
| Change business settings | Yes | No | No | No |
| Toggle AI automation | Yes | No | No | No |
| Create products | Yes | Yes | Yes | No |
| Record movements | Yes | Yes | No | No |
| Create purchase orders | Yes | No | Yes | No |
| Approve AI-drafted orders | Yes | No | Yes | No |
| View reports and audit logs | Yes | Yes | Yes | Yes |

Minimal implementation:

- Store role metadata in Clerk public/private metadata or a workspace membership entity.
- Add a backend dependency such as `require_role("owner", "purchasing_lead")`.
- Gate settings, AI automation, order approval, and report export routes.
- Mirror role affordances in the UI by disabling or hiding restricted actions.

## 4. RAG And Vector Retrieval

Current state:

- Workspace chat uses the current workspace snapshot and deterministic fallbacks.
- There is no vector index yet.

Why this matters:

- Historical reports, supplier notes, late-order history, and previous AI decisions become valuable context as the workspace grows.
- Retrieval avoids sending the entire workspace to the LLM and makes long-running businesses easier to query.

Target retrieval sources:

- replenishment report summaries and recommendations
- supplier scorecards and notes
- late-order events
- order notification events
- AI audit summaries
- owner-facing monthly/weekly briefs

Minimal implementation:

- Add a small retrieval module that converts workspace events into text chunks.
- Embed chunks with the selected embedding provider.
- Store vectors in Chroma for local development, then move to S3 Vectors, pgvector, OpenSearch, or a DynamoDB-adjacent vector store for deployment.
- Update chat so it retrieves top-k relevant chunks and cites which workspace artifacts informed the answer.

## 5. DynamoDB Scaling

Current state:

- Each workspace is stored as a single DynamoDB item keyed by `owner_user_id`.
- This is simple, excellent for demos, and easy to reason about.

Where it breaks:

- DynamoDB item size limit is 400 KB.
- Movement history, order history, reports, audit logs, and notification events will eventually exceed that limit.
- Write contention can also increase because every update rewrites the workspace item.

Migration design:

```text
PK = WORKSPACE#{owner_user_id}
SK = BUSINESS

PK = WORKSPACE#{owner_user_id}
SK = PRODUCT#{product_id}

PK = WORKSPACE#{owner_user_id}
SK = MOVEMENT#{created_at}#{movement_id}

PK = WORKSPACE#{owner_user_id}
SK = ORDER#{created_at}#{order_id}

PK = WORKSPACE#{owner_user_id}
SK = REPORT#{generated_at}#{report_id}

PK = WORKSPACE#{owner_user_id}
SK = AI_AUDIT#{created_at}#{audit_id}
```

Useful indexes:

- `GSI1PK = WORKSPACE#{owner_user_id}#ENTITY#{type}` with `GSI1SK = created_at`
- `GSI2PK = SUPPLIER#{supplier_id}` with `GSI2SK = expected_delivery_date`
- `GSI3PK = PRODUCT#{product_id}` with `GSI3SK = occurred_at`

Minimal implementation:

- Keep the current workspace document as the local/demo adapter.
- Add a second store implementation for multi-item DynamoDB.
- Write migration/export code that can split an existing workspace item into typed records.

## 6. PR And Review Discipline

Current state:

- Main branch contains functional commit history.
- There is CI/CD, but no visible issue/PR workflow.

Why this matters:

- Hiring teams often assess whether a candidate understands review culture, not only whether code works.

Recommended workflow:

1. Open a GitHub issue for each meaningful feature or hardening task.
2. Create a branch named `feature/audit-page` or `hardening/sqs-worker-path`.
3. Open a self-authored PR with context, screenshots, tests, and risks.
4. Let CI run.
5. Squash or merge after review.

This repository now includes issue and PR templates to make that workflow visible.
