#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AWS_REGION="${DEFAULT_AWS_REGION:-us-east-1}"
PROJECT_NAME="${PROJECT_NAME:-supplychain-ai}"
DYNAMODB_TABLE_NAME="${DYNAMODB_TABLE_NAME:-supplychain-ai-workspaces}"
ALARM_EMAIL="${ALARM_EMAIL:-}"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

AWS_REGION="${DEFAULT_AWS_REGION:-$AWS_REGION}"
DYNAMODB_TABLE_NAME="${DYNAMODB_TABLE_NAME:-supplychain-ai-workspaces}"

required_env=(
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
  CLERK_JWKS_URL
  CLERK_ISSUER
  OPENAI_API_KEY
  RESEND_API_KEY
  RESEND_FROM_EMAIL
)

for env_name in "${required_env[@]}"; do
  if [[ -z "${!env_name:-}" ]]; then
    echo "Missing required environment variable: ${env_name}" >&2
    exit 1
  fi
done

unset NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL
unset NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL

ensure_dynamodb_table_in_state() {
  local tf_dir="$1"
  local table_name="$2"

  if terraform -chdir="$tf_dir" state show aws_dynamodb_table.workspace >/dev/null 2>&1; then
    return 0
  fi

  if aws dynamodb describe-table --table-name "$table_name" --region "$AWS_REGION" >/dev/null 2>&1; then
    echo "Terraform state is missing DynamoDB table ${table_name}; importing existing table..."
    terraform -chdir="$tf_dir" import aws_dynamodb_table.workspace "$table_name"
  fi
}

echo "Deploying ${PROJECT_NAME} to AWS region ${AWS_REGION}."
echo "Packaging backend Lambda..."
(
  cd "$ROOT_DIR/backend/api"
  ./package_lambda.sh
)

echo "Applying DynamoDB layer..."
(
  cd "$ROOT_DIR/terraform/2_database"
  terraform init -input=false
  ensure_dynamodb_table_in_state "$PWD" "$DYNAMODB_TABLE_NAME"
  terraform apply -auto-approve \
    -var="aws_region=${AWS_REGION}" \
    -var="project_name=${PROJECT_NAME}" \
    -var="dynamodb_table_name=${DYNAMODB_TABLE_NAME}"
)

echo "Applying frontend/API layer..."
(
  cd "$ROOT_DIR/terraform/4_frontend"
  terraform init -input=false
  TF_VAR_openai_api_key="${OPENAI_API_KEY}" \
  TF_VAR_resend_api_key="${RESEND_API_KEY}" \
  terraform apply -auto-approve \
    -var="aws_region=${AWS_REGION}" \
    -var="project_name=${PROJECT_NAME}" \
    -var="enable_api_lambda=true" \
    -var="dynamodb_table_name=${DYNAMODB_TABLE_NAME}" \
    -var="clerk_jwks_url=${CLERK_JWKS_URL}" \
    -var="clerk_issuer=${CLERK_ISSUER}" \
    -var="openai_model=${OPENAI_MODEL:-gpt-5-nano}" \
    -var="resend_from_email=${RESEND_FROM_EMAIL}" \
    -var='api_lambda_environment={
      ALLOW_DEV_AUTH_FALLBACK = "false",
      DYNAMODB_USE_REMOTE = "true",
      DYNAMODB_USE_LOCAL = "false",
      DYNAMODB_FALLBACK_TO_FILE = "false",
      OPENAI_REASONING_EFFORT = "low",
      AI_AUTO_ORDER_DRAFT_FIRST = "true",
      AI_AUTO_ORDER_MAX_SPEND = "250000"
    }'
)

api_url="$(cd "$ROOT_DIR/terraform/4_frontend" && terraform output -raw api_gateway_url)"
bucket_name="$(cd "$ROOT_DIR/terraform/4_frontend" && terraform output -raw frontend_bucket_name)"
distribution_id="$(cd "$ROOT_DIR/terraform/4_frontend" && terraform output -raw cloudfront_distribution_id)"
frontend_url="$(cd "$ROOT_DIR/terraform/4_frontend" && terraform output -raw frontend_url)"
api_id="$(cd "$ROOT_DIR/terraform/4_frontend" && terraform output -raw api_gateway_id)"
lambda_name="$(cd "$ROOT_DIR/terraform/4_frontend" && terraform output -raw lambda_function_name)"

echo "Building static frontend for ${api_url}..."
(
  cd "$ROOT_DIR/frontend"
  NEXT_PUBLIC_STATIC_EXPORT=true \
  NEXT_PUBLIC_API_URL="${api_url}" \
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}" \
  NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL="" \
  NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL="" \
  NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL="/dashboard" \
  NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL="/dashboard" \
  npm run build:static
)

echo "Uploading frontend assets to s3://${bucket_name}..."
aws s3 sync "$ROOT_DIR/frontend/out/" "s3://${bucket_name}/" --delete --region "$AWS_REGION"

echo "Creating CloudFront invalidation..."
aws cloudfront create-invalidation --distribution-id "$distribution_id" --paths "/*" --region "$AWS_REGION" >/dev/null

echo "Applying monitoring layer..."
(
  cd "$ROOT_DIR/terraform/5_enterprise"
  terraform init -input=false
  terraform apply -auto-approve \
    -var="aws_region=${AWS_REGION}" \
    -var="project_name=${PROJECT_NAME}" \
    -var="cloudfront_distribution_id=${distribution_id}" \
    -var="api_gateway_id=${api_id}" \
    -var="lambda_function_name=${lambda_name}" \
    -var="alarm_email=${ALARM_EMAIL}"
)

echo "Deployment complete."
echo "Frontend: ${frontend_url}"
echo "API: ${api_url}"
echo "Health: ${api_url}/health"
