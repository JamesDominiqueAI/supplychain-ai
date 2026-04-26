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

terraform_state_has() {
  local tf_dir="$1"
  local resource_address="$2"
  terraform -chdir="$tf_dir" state show "$resource_address" >/dev/null 2>&1
}

terraform_import_if_missing() {
  local tf_dir="$1"
  local resource_address="$2"
  local import_id="$3"
  shift 3
  local terraform_args=("$@")

  if terraform_state_has "$tf_dir" "$resource_address"; then
    return 0
  fi

  echo "Terraform state is missing ${resource_address}; importing existing resource ${import_id}..."
  terraform -chdir="$tf_dir" import "${terraform_args[@]}" "$resource_address" "$import_id"
}

ensure_frontend_api_resources_in_state() {
  local tf_dir="$1"
  local bucket_name="$2"
  local name_prefix="$3"
  local terraform_args=(
    -var="aws_region=${AWS_REGION}"
    -var="project_name=${name_prefix}"
    -var="enable_api_lambda=true"
    -var="api_lambda_provisioned_concurrency=0"
    -var="dynamodb_table_name=${DYNAMODB_TABLE_NAME}"
    -var="clerk_jwks_url=${CLERK_JWKS_URL}"
    -var="clerk_issuer=${CLERK_ISSUER}"
    -var="openai_model=${OPENAI_MODEL:-gpt-5-nano}"
    -var="resend_from_email=${RESEND_FROM_EMAIL}"
    -var="enable_scheduled_agent=${ENABLE_SCHEDULED_AGENT:-false}"
    -var="scheduled_agent_owner_id=${SCHEDULED_AGENT_OWNER_ID:-}"
    -var="scheduled_agent_allow_drafts=${SCHEDULED_AGENT_ALLOW_DRAFTS:-false}"
    -var="scheduled_agent_expression=${SCHEDULED_AGENT_EXPRESSION:-rate(1 day)}"
  )
  local role_name="${name_prefix}-api-lambda-role"
  local role_policy_name="${name_prefix}-api-lambda-dynamodb"
  local lambda_name="${name_prefix}-api"
  local lambda_alias_name="live"
  local api_name="${name_prefix}-api-gateway"
  local oac_name="${name_prefix}-frontend-oac"
  local scheduled_agent_rule_name="${name_prefix}-scheduled-agent"
  local basic_role_policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

  if aws s3api head-bucket --bucket "$bucket_name" --region "$AWS_REGION" >/dev/null 2>&1; then
    terraform_import_if_missing "$tf_dir" aws_s3_bucket.frontend "$bucket_name" "${terraform_args[@]}"
    terraform_import_if_missing "$tf_dir" aws_s3_bucket_public_access_block.frontend "$bucket_name" "${terraform_args[@]}"
    terraform_import_if_missing "$tf_dir" aws_s3_bucket_versioning.frontend "$bucket_name" "${terraform_args[@]}"
    terraform_import_if_missing "$tf_dir" aws_s3_bucket_server_side_encryption_configuration.frontend "$bucket_name" "${terraform_args[@]}"
    terraform_import_if_missing "$tf_dir" aws_s3_bucket_website_configuration.frontend "$bucket_name" "${terraform_args[@]}"
    terraform_import_if_missing "$tf_dir" aws_s3_bucket_policy.frontend "$bucket_name" "${terraform_args[@]}"
  fi

  local oac_id
  oac_id="$(aws cloudfront list-origin-access-controls \
    --query "OriginAccessControlList.Items[?Name=='${oac_name}'].Id | [0]" \
    --output text 2>/dev/null || true)"
  if [[ -n "$oac_id" && "$oac_id" != "None" ]]; then
    terraform_import_if_missing "$tf_dir" aws_cloudfront_origin_access_control.frontend "$oac_id" "${terraform_args[@]}"
  fi

  local distribution_id
  distribution_id="$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Comment=='${name_prefix} frontend CDN'].Id | [0]" \
    --output text 2>/dev/null || true)"
  if [[ -n "$distribution_id" && "$distribution_id" != "None" ]]; then
    terraform_import_if_missing "$tf_dir" aws_cloudfront_distribution.frontend "$distribution_id" "${terraform_args[@]}"
  fi

  if aws iam get-role --role-name "$role_name" >/dev/null 2>&1; then
    terraform_import_if_missing "$tf_dir" 'aws_iam_role.api_lambda[0]' "$role_name" "${terraform_args[@]}"
    if aws iam list-attached-role-policies --role-name "$role_name" \
      --query "AttachedPolicies[?PolicyArn=='${basic_role_policy_arn}'].PolicyArn | [0]" \
      --output text 2>/dev/null | grep -q '^arn:'; then
      terraform_import_if_missing "$tf_dir" 'aws_iam_role_policy_attachment.api_lambda_basic[0]' "${role_name}/${basic_role_policy_arn}" "${terraform_args[@]}"
    fi
    if aws iam get-role-policy --role-name "$role_name" --policy-name "$role_policy_name" >/dev/null 2>&1; then
      terraform_import_if_missing "$tf_dir" 'aws_iam_role_policy.api_lambda_dynamodb[0]' "${role_name}:${role_policy_name}" "${terraform_args[@]}"
    fi
  fi

  if aws lambda get-function --function-name "$lambda_name" --region "$AWS_REGION" >/dev/null 2>&1; then
    terraform_import_if_missing "$tf_dir" 'aws_lambda_function.api[0]' "$lambda_name" "${terraform_args[@]}"
    local lambda_permission_target="${lambda_name}"
    local lambda_policy_args=(--function-name "$lambda_name" --region "$AWS_REGION")
    if aws lambda get-alias --function-name "$lambda_name" --name "$lambda_alias_name" --region "$AWS_REGION" >/dev/null 2>&1; then
      terraform_import_if_missing "$tf_dir" 'aws_lambda_alias.api_live[0]' "${lambda_name}/${lambda_alias_name}" "${terraform_args[@]}"
      lambda_permission_target="${lambda_name}:${lambda_alias_name}"
      lambda_policy_args+=(--qualifier "$lambda_alias_name")
      if aws lambda get-provisioned-concurrency-config \
        --function-name "$lambda_name" \
        --qualifier "$lambda_alias_name" \
        --region "$AWS_REGION" >/dev/null 2>&1; then
        terraform_import_if_missing "$tf_dir" 'aws_lambda_provisioned_concurrency_config.api_live[0]' "${lambda_name}/${lambda_alias_name}" "${terraform_args[@]}"
      fi
    fi
    if aws lambda get-policy "${lambda_policy_args[@]}" \
      --query "Policy" --output text 2>/dev/null | grep -q 'AllowExecutionFromApiGateway'; then
      terraform_import_if_missing "$tf_dir" 'aws_lambda_permission.api_gateway[0]' "${lambda_permission_target}/AllowExecutionFromApiGateway" "${terraform_args[@]}"
    fi
  fi

  if [[ "${ENABLE_SCHEDULED_AGENT:-false}" == "true" && -n "${SCHEDULED_AGENT_OWNER_ID:-}" ]] && \
    aws events describe-rule --name "$scheduled_agent_rule_name" --region "$AWS_REGION" >/dev/null 2>&1; then
    terraform_import_if_missing "$tf_dir" 'aws_cloudwatch_event_rule.scheduled_agent[0]' "$scheduled_agent_rule_name" "${terraform_args[@]}"
  fi

  local api_id
  api_id="$(aws apigatewayv2 get-apis \
    --query "Items[?Name=='${api_name}'].ApiId | [0]" \
    --output text 2>/dev/null || true)"
  if [[ -n "$api_id" && "$api_id" != "None" ]]; then
    terraform_import_if_missing "$tf_dir" 'aws_apigatewayv2_api.main[0]' "$api_id" "${terraform_args[@]}"

    local integration_id
    integration_id="$(aws apigatewayv2 get-integrations --api-id "$api_id" \
      --query 'Items[0].IntegrationId' --output text 2>/dev/null || true)"
    if [[ -n "$integration_id" && "$integration_id" != "None" ]]; then
      terraform_import_if_missing "$tf_dir" 'aws_apigatewayv2_integration.lambda[0]' "${api_id}/${integration_id}" "${terraform_args[@]}"
    fi

    local proxy_route_id
    proxy_route_id="$(aws apigatewayv2 get-routes --api-id "$api_id" \
      --query "Items[?RouteKey=='ANY /{proxy+}'].RouteId | [0]" --output text 2>/dev/null || true)"
    if [[ -n "$proxy_route_id" && "$proxy_route_id" != "None" ]]; then
      terraform_import_if_missing "$tf_dir" 'aws_apigatewayv2_route.proxy[0]' "${api_id}/${proxy_route_id}" "${terraform_args[@]}"
    fi

    local root_route_id
    root_route_id="$(aws apigatewayv2 get-routes --api-id "$api_id" \
      --query "Items[?RouteKey=='ANY /'].RouteId | [0]" --output text 2>/dev/null || true)"
    if [[ -n "$root_route_id" && "$root_route_id" != "None" ]]; then
      terraform_import_if_missing "$tf_dir" 'aws_apigatewayv2_route.root[0]' "${api_id}/${root_route_id}" "${terraform_args[@]}"
    fi

    if aws apigatewayv2 get-stage --api-id "$api_id" --stage-name '$default' >/dev/null 2>&1; then
      terraform_import_if_missing "$tf_dir" 'aws_apigatewayv2_stage.default[0]' "${api_id}/\$default" "${terraform_args[@]}"
    fi
  fi
}

echo "Deploying ${PROJECT_NAME} to AWS region ${AWS_REGION}."
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
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
  ensure_frontend_api_resources_in_state "$PWD" "${PROJECT_NAME}-frontend-${AWS_ACCOUNT_ID}" "$PROJECT_NAME"
  TF_VAR_openai_api_key="${OPENAI_API_KEY}" \
  TF_VAR_resend_api_key="${RESEND_API_KEY}" \
  terraform apply -auto-approve \
    -var="aws_region=${AWS_REGION}" \
    -var="project_name=${PROJECT_NAME}" \
    -var="enable_api_lambda=true" \
    -var="api_lambda_provisioned_concurrency=0" \
    -var="dynamodb_table_name=${DYNAMODB_TABLE_NAME}" \
    -var="clerk_jwks_url=${CLERK_JWKS_URL}" \
    -var="clerk_issuer=${CLERK_ISSUER}" \
    -var="openai_model=${OPENAI_MODEL:-gpt-5-nano}" \
    -var="resend_from_email=${RESEND_FROM_EMAIL}" \
    -var="enable_scheduled_agent=${ENABLE_SCHEDULED_AGENT:-false}" \
    -var="scheduled_agent_owner_id=${SCHEDULED_AGENT_OWNER_ID:-}" \
    -var="scheduled_agent_allow_drafts=${SCHEDULED_AGENT_ALLOW_DRAFTS:-false}" \
    -var="scheduled_agent_expression=${SCHEDULED_AGENT_EXPRESSION:-rate(1 day)}" \
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
