# AWS Deployment Runbook

This project deploys as a practical serverless AWS application:

- DynamoDB workspace persistence
- FastAPI backend packaged as Lambda
- API Gateway HTTP API
- static Next.js frontend in S3
- CloudFront CDN
- CloudWatch dashboard and alarms

## One-Command Deploy

From the project root:

```bash
bash scripts/deploy_aws.sh
```

The script reads `.env`, packages the backend, applies Terraform, builds the frontend with the real API Gateway URL, uploads static assets to S3, invalidates CloudFront, and applies monitoring.

## Required Environment

The deployment expects these values in `.env`:

```bash
DEFAULT_AWS_REGION=us-east-1
CLERK_JWKS_URL=https://your-clerk-instance/.well-known/jwks.json
CLERK_ISSUER=https://your-clerk-instance
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5-nano
RESEND_API_KEY=...
RESEND_FROM_EMAIL=onboarding@resend.dev
```

## Clerk Production Setup

For the deployed app, use a Clerk production instance or live keys. Development keys can work for local testing, but they are fragile for a CloudFront deployment and may hit development restrictions.

In Clerk, configure:

```text
Allowed origin:
https://d3s6kuid14g7p7.cloudfront.net

Sign-in URL:
https://d3s6kuid14g7p7.cloudfront.net/login

Sign-up URL:
https://d3s6kuid14g7p7.cloudfront.net/login

After sign-in URL:
https://d3s6kuid14g7p7.cloudfront.net/dashboard

After sign-up URL:
https://d3s6kuid14g7p7.cloudfront.net/dashboard
```

Then update `.env` with the live Clerk values:

```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=<your-production-clerk-publishable-key>
CLERK_SECRET_KEY=<your-production-clerk-secret-key>
CLERK_ISSUER=https://your-live-clerk-domain
CLERK_JWKS_URL=https://your-live-clerk-domain/.well-known/jwks.json
ALLOW_DEV_AUTH_FALLBACK=false
```

If the deployed app returns `401 Invalid session token`, run this in the browser console while signed in:

```js
const token = await window.Clerk.session.getToken();

await fetch("https://3oqte8cx9g.execute-api.us-east-1.amazonaws.com/api/auth/debug", {
  headers: { Authorization: `Bearer ${token}` },
})
  .then((response) => response.json())
  .then(console.log);
```

The key fields are `token_issuer`, `configured_issuer`, and `verification_error`.

Optional:

```bash
ALARM_EMAIL=you@example.com
PROJECT_NAME=supplychain-ai
DYNAMODB_TABLE_NAME=supplychain-ai-workspaces
```

## Current AWS Blocker

The current AWS identity is:

```text
arn:aws:iam::285407029618:user/aiengineer
```

Deployment is currently blocked because this user does not have permission to create or inspect the DynamoDB table:

```text
dynamodb:CreateTable
dynamodb:DescribeTable
```

The same user is also blocked from inspecting its own IAM policies, so an AWS admin needs to attach deployment permissions.

## Minimum Practical Policy For This Capstone Deploy

Attach a policy like this to the deployment user or, preferably, to a temporary deployment role that the user can assume:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DynamoDBWorkspaceTable",
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DescribeTable",
        "dynamodb:UpdateTable",
        "dynamodb:DeleteTable",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:TagResource",
        "dynamodb:ListTagsOfResource"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:285407029618:table/supplychain-ai-workspaces"
    },
    {
      "Sid": "LambdaApiGatewayAndLogs",
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:GetFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:DeleteFunction",
        "lambda:AddPermission",
        "lambda:RemovePermission",
        "lambda:TagResource",
        "apigateway:*",
        "logs:CreateLogGroup",
        "logs:DescribeLogGroups",
        "logs:PutRetentionPolicy"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IamForLambdaRole",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:GetRole",
        "iam:DeleteRole",
        "iam:TagRole",
        "iam:PassRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:GetRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:ListRolePolicies",
        "iam:ListAttachedRolePolicies"
      ],
      "Resource": "arn:aws:iam::285407029618:role/supplychain-ai-*"
    },
    {
      "Sid": "FrontendBucketAndCdn",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:GetBucket*",
        "s3:ListBucket",
        "s3:PutBucket*",
        "s3:DeleteBucket*",
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "cloudfront:CreateDistribution",
        "cloudfront:GetDistribution",
        "cloudfront:GetDistributionConfig",
        "cloudfront:UpdateDistribution",
        "cloudfront:DeleteDistribution",
        "cloudfront:CreateInvalidation",
        "cloudfront:CreateOriginAccessControl",
        "cloudfront:GetOriginAccessControl",
        "cloudfront:UpdateOriginAccessControl",
        "cloudfront:DeleteOriginAccessControl",
        "cloudfront:TagResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "Monitoring",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutDashboard",
        "cloudwatch:GetDashboard",
        "cloudwatch:DeleteDashboards",
        "cloudwatch:PutMetricAlarm",
        "cloudwatch:DescribeAlarms",
        "cloudwatch:DeleteAlarms",
        "sns:CreateTopic",
        "sns:GetTopicAttributes",
        "sns:SetTopicAttributes",
        "sns:Subscribe",
        "sns:Unsubscribe",
        "sns:DeleteTopic",
        "sns:TagResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ReadAccountContext",
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

For a short-lived capstone deployment, an admin can alternatively attach `AdministratorAccess`, deploy, then replace it with tighter runtime permissions afterward.

## After Permissions Are Added

Run:

```bash
bash scripts/deploy_aws.sh
```

When it succeeds, capture:

- CloudFront frontend URL
- API Gateway `/health` URL
- DynamoDB table screenshot
- Lambda logs in CloudWatch
- CloudWatch dashboard screenshot
- one live product/sale/report/order demo
