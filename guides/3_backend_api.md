# Guide 3: Backend API

## Backend Responsibilities

- auth and tenant scoping
- CRUD for products, suppliers, locations, and POs
- inventory calculations
- CSV import
- job submission and polling
- report retrieval

## Suggested Endpoints

- `GET /api/business`
- `GET /api/products`
- `POST /api/products`
- `GET /api/suppliers`
- `POST /api/suppliers`
- `GET /api/inventory/health`
- `POST /api/inventory/movements`
- `POST /api/import/products`
- `POST /api/import/movements`
- `POST /api/analysis/replenishment`
- `GET /api/jobs/{job_id}`
- `GET /api/reports`
- `GET /api/reports/{report_id}`

## Async Workflow

Large analysis tasks should not run inline.

Use:
- API -> create job row
- API -> push to SQS
- planner lambda -> orchestrate specialist agents
- specialists -> write results
- narrator -> generate final report
- frontend -> poll status

## Guardrails

- strict tenant checks on every query
- SKU validation
- quantity validation
- no AI-generated updates directly mutating stock balances
- require explanations for purchase recommendations
