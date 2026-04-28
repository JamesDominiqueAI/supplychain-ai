FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_LINK_MODE=copy \
    APP_ENV=development \
    BACKEND_HOST=0.0.0.0 \
    BACKEND_PORT=8010 \
    ALLOW_DEV_AUTH_FALLBACK=true \
    DYNAMODB_USE_LOCAL=true \
    DYNAMODB_USE_REMOTE=false \
    DYNAMODB_FALLBACK_TO_FILE=true \
    LOCAL_STATE_PATH=/app/data/workspaces

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY backend ./backend

RUN uv sync --frozen --package supplychain-api --no-dev

EXPOSE 8010

CMD ["uv", "run", "--frozen", "--no-sync", "--package", "supplychain-api", "python", "backend/api/main.py"]
