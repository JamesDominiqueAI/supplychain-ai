# API Module

This module contains the active HTTP and Lambda entrypoints for SupplyChain AI.

Implemented responsibilities:

- FastAPI app in `main.py`
- Clerk auth/debug endpoints
- workspace, product, supplier, inventory, order, report, AI, agent, notification, and observability routes
- request latency/error metrics middleware
- Lambda adapter in `lambda_handler.py`
- Lambda package script

Local development:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --package supplychain-api python backend/api/main.py
```

Lambda packaging:

```bash
cd backend/api
chmod +x package_lambda.sh
./package_lambda.sh
```

This creates `backend/api/api_lambda.zip` for the Terraform API deployment path.
