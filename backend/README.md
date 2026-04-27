# Backend

The backend is a FastAPI workspace API with deterministic supply-chain logic, guarded AI features, local/DynamoDB persistence, and Lambda compatibility.

Implemented modules:

- `api/`: FastAPI routes, auth dependency wiring, observability middleware, Lambda handler, and packaging.
- `database/`: Pydantic schemas, DynamoDB/local workspace store, guardrails, notifications, and replenishment service.
- `planner/`, `demand/`, `replenishment/`, `supplier_risk/`, `narrator/`: domain-facing module folders retained as documentation boundaries for the agent and analytics responsibilities now implemented through the shared store/service layer.

Local API:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python backend/api/main.py
```

Project evaluation:

```bash
python scripts/evaluate_project.py
```
