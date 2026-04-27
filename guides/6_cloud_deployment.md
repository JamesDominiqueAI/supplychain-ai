# Guide 6: Cloud Deployment

The current AWS target is a practical serverless deployment:

- static Next.js export in private S3
- CloudFront CDN with origin access control
- FastAPI packaged as Lambda with Mangum
- API Gateway HTTP API
- DynamoDB workspace table
- optional EventBridge scheduled operations agent
- CloudWatch dashboard and alarms
- SNS email alert topic

## Terraform Phases

### 1. Foundation

`terraform/1_foundation` defines shared provider/project setup. It is intentionally small because most real resources live in later phases.

### 2. Database

`terraform/2_database` provisions the active data layer:

- DynamoDB table keyed by `owner_user_id`
- on-demand billing
- server-side encryption
- optional point-in-time recovery

### 3. Agents

`terraform/3_agents` currently reserves the async-analysis layer. The app runs agents through the API today, while this phase remains the future home for SQS queues and worker Lambdas.

### 4. Frontend and API

`terraform/4_frontend` provisions:

- private frontend S3 bucket
- CloudFront distribution
- SPA fallback behavior
- optional backend Lambda
- API Gateway HTTP API
- Lambda alias and optional provisioned concurrency
- scheduled EventBridge trigger for operations-agent runs

### 5. Enterprise

`terraform/5_enterprise` provisions:

- SNS alert topic
- optional email subscription
- CloudWatch operations dashboard
- CloudFront 5xx alarm
- Lambda error alarm
- API Gateway visibility widgets when IDs are provided

## One-Command Deploy

From the project root:

```bash
bash scripts/deploy_aws.sh
```

The script packages the backend Lambda, applies Terraform, builds the frontend with the deployed API URL, uploads static assets to S3, invalidates CloudFront, and applies monitoring.

## Required Environment

Use `.env` or CI secrets for:

- `DEFAULT_AWS_REGION`
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `CLERK_SECRET_KEY`
- `CLERK_JWKS_URL`
- `CLERK_ISSUER`
- `OPENAI_API_KEY`
- `RESEND_API_KEY`
- `RESEND_FROM_EMAIL`

Optional:

- `ALARM_EMAIL`
- `DYNAMODB_TABLE_NAME`
- `OPENAI_MODEL`
- scheduled agent settings

## Production Notes

- `DYNAMODB_AUTO_CREATE=false` in Lambda; Terraform owns the table.
- `CORS_ORIGINS` includes local development origins and the CloudFront domain.
- Clerk production origins must include the CloudFront URL.
- Resend can only send broadly after the sending domain is verified.
- Deployment currently depends on the AWS identity having permissions for DynamoDB, Lambda, API Gateway, IAM roles, S3, CloudFront, CloudWatch, and SNS.
