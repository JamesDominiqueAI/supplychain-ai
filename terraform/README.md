# Terraform

The repository uses phased Terraform so each deployment concern can be applied and debugged independently.

Current phases:

- `1_foundation/`: shared provider/project foundation.
- `2_database/`: DynamoDB workspace table.
- `3_agents/`: reserved async-agent phase for future SQS/worker expansion.
- `4_frontend/`: S3 frontend bucket, CloudFront distribution, optional Lambda API, API Gateway, and scheduled agent trigger.
- `5_enterprise/`: SNS alerts, CloudWatch dashboard, and CloudFront/API/Lambda monitoring.

The normal deployment path is:

```bash
bash scripts/deploy_aws.sh
```

That script packages the API, applies the needed Terraform layers, builds the frontend with the deployed API URL, uploads static assets, invalidates CloudFront, and applies monitoring.
