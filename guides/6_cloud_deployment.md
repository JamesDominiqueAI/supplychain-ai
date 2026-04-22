# Guide 6: Cloud Deployment

## Recommended AWS Layout

### Foundation

- Clerk for auth
- S3 for frontend hosting
- CloudFront CDN
- API Gateway + Lambda for backend

### Data

- Aurora Serverless v2 PostgreSQL
- Data API for serverless access

### AI / Jobs

- SQS queue for async analysis
- Lambda workers for planner and specialists
- Bedrock or OpenAI model provider

### Observability

- CloudWatch logs
- CloudWatch dashboards
- CloudWatch alarms

## Deployment Phases

1. auth + frontend shell
2. database + API CRUD
3. async jobs + agent orchestration
4. reporting + dashboards
5. enterprise monitoring and controls
