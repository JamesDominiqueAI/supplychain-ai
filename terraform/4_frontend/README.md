# Terraform Phase 4: Frontend And API

This phase provisions the deployable frontend and optional backend API.

Current resources:

- private S3 bucket for static frontend assets
- CloudFront distribution with origin access control
- SPA-style fallback to `index.html`
- optional FastAPI Lambda
- API Gateway HTTP API
- Lambda alias
- optional provisioned concurrency
- optional EventBridge scheduled operations-agent trigger
- CORS configuration for local and deployed origins

The frontend has a static export build path:

```bash
cd frontend
npm run build:static
```

The backend package is created with:

```bash
cd backend/api
./package_lambda.sh
```

In normal usage, `scripts/deploy_aws.sh` handles both steps and uploads the final frontend artifacts.
