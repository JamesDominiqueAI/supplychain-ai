# API Module

Start here if you want to implement the HTTP layer first.

Suggested first endpoints:
- products CRUD
- suppliers CRUD
- inventory movements
- inventory health summary
- replenishment job trigger

Local development:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python main.py
```

Lambda packaging:

```bash
cd backend/api
chmod +x package_lambda.sh
./package_lambda.sh
```

This creates `backend/api/api_lambda.zip`, which matches the Terraform frontend/API phase.
