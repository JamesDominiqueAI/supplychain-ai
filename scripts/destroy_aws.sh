#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AWS_REGION="${DEFAULT_AWS_REGION:-us-east-1}"
PROJECT_NAME="${PROJECT_NAME:-supplychain-ai}"
DYNAMODB_TABLE_NAME="${DYNAMODB_TABLE_NAME:-supplychain-ai-workspaces}"
CONFIRM_PHRASE="destroy ${PROJECT_NAME}"
SKIP_BUCKET_EMPTY="${SKIP_BUCKET_EMPTY:-false}"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

AWS_REGION="${DEFAULT_AWS_REGION:-$AWS_REGION}"
DYNAMODB_TABLE_NAME="${DYNAMODB_TABLE_NAME:-supplychain-ai-workspaces}"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<EOF
Destroy AWS resources for ${PROJECT_NAME}.

Usage:
  scripts/destroy_aws.sh

Environment:
  DEFAULT_AWS_REGION       AWS region. Default: us-east-1
  PROJECT_NAME             Terraform project name. Default: supplychain-ai
  DYNAMODB_TABLE_NAME      DynamoDB table name. Default: supplychain-ai-workspaces
  SKIP_BUCKET_EMPTY=true   Skip the S3 bucket empty step.

This script destroys Terraform layers in reverse order:
  1. terraform/5_enterprise
  2. terraform/4_frontend
  3. terraform/3_agents
  4. terraform/2_database
  5. terraform/1_foundation

It is destructive and requires typing:
  ${CONFIRM_PHRASE}
EOF
  exit 0
fi

cat <<EOF
WARNING: this will delete AWS resources for ${PROJECT_NAME}.

Region: ${AWS_REGION}
DynamoDB table: ${DYNAMODB_TABLE_NAME}

Terraform layers will be destroyed in reverse order:
  - terraform/5_enterprise
  - terraform/4_frontend
  - terraform/3_agents
  - terraform/2_database
  - terraform/1_foundation

Type exactly "${CONFIRM_PHRASE}" to continue:
EOF

read -r confirmation
if [[ "$confirmation" != "$CONFIRM_PHRASE" ]]; then
  echo "Confirmation did not match. Nothing was destroyed."
  exit 1
fi

run_if_state_exists() {
  local layer_path="$1"
  shift

  if [[ ! -f "$layer_path/terraform.tfstate" ]]; then
    echo "Skipping ${layer_path}: no local terraform.tfstate found."
    return 0
  fi

  (
    cd "$layer_path"
    terraform init -input=false
    terraform destroy -auto-approve "$@"
  )
}

frontend_bucket_name=""
if [[ -f "$ROOT_DIR/terraform/4_frontend/terraform.tfstate" ]]; then
  frontend_bucket_name="$(
    cd "$ROOT_DIR/terraform/4_frontend"
    terraform output -raw frontend_bucket_name 2>/dev/null || true
  )"
fi

if [[ -n "$frontend_bucket_name" && "$SKIP_BUCKET_EMPTY" != "true" ]]; then
  echo "Emptying frontend bucket s3://${frontend_bucket_name} before Terraform destroy..."
  aws s3 rm "s3://${frontend_bucket_name}" --recursive --region "$AWS_REGION"
fi

echo "Destroying enterprise monitoring layer..."
run_if_state_exists "$ROOT_DIR/terraform/5_enterprise" \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}"

echo "Destroying frontend/API layer..."
run_if_state_exists "$ROOT_DIR/terraform/4_frontend" \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}" \
  -var="enable_api_lambda=true" \
  -var="dynamodb_table_name=${DYNAMODB_TABLE_NAME}" \
  -var="force_destroy_frontend_bucket=true"

echo "Destroying agents layer..."
run_if_state_exists "$ROOT_DIR/terraform/3_agents" \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}"

echo "Destroying database layer..."
run_if_state_exists "$ROOT_DIR/terraform/2_database" \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}" \
  -var="dynamodb_table_name=${DYNAMODB_TABLE_NAME}"

echo "Destroying foundation layer..."
run_if_state_exists "$ROOT_DIR/terraform/1_foundation" \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}"

echo "Destroy complete."
