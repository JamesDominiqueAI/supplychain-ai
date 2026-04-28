# Backend

The backend is a FastAPI workspace API with deterministic supply-chain logic, guarded AI features, local/DynamoDB persistence, and Lambda compatibility.

Implemented modules:

- `api/`: FastAPI routes, auth dependency wiring, observability middleware, Lambda handler, and packaging.
- `database/`: Pydantic schemas, DynamoDB/local workspace store, guardrails, notifications, and replenishment service.
- `planner/`, `demand/`, `replenishment/`, `supplier_risk/`, `narrator/`: domain-facing module folders retained as documentation boundaries for the agent and analytics responsibilities now implemented through the shared store/service layer.

Local API:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --package supplychain-api python backend/api/main.py
```

Docker image:

```bash
docker build -f backend/Dockerfile -t supplychain-ai-backend .
docker run --rm -p 8010:8010 supplychain-ai-backend
```

Project evaluation:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --package supplychain-api python scripts/evaluate_project.py
```
