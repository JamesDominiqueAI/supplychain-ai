variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short project name used in resource naming"
  type        = string
  default     = "supplychain-ai"
}

variable "frontend_bucket_name" {
  description = "Optional override for the frontend bucket name"
  type        = string
  default     = ""
}

variable "cloudfront_price_class" {
  description = "CloudFront price class"
  type        = string
  default     = "PriceClass_100"
}

variable "frontend_aliases" {
  description = "Optional custom domain aliases for the CloudFront distribution"
  type        = list(string)
  default     = []
}

variable "acm_certificate_arn" {
  description = "Optional ACM certificate ARN in us-east-1 for custom domains"
  type        = string
  default     = ""
}

variable "force_destroy_frontend_bucket" {
  description = "Allow Terraform to delete a non-empty frontend bucket"
  type        = bool
  default     = false
}

variable "enable_api_lambda" {
  description = "Create the backend Lambda and API Gateway resources in this phase"
  type        = bool
  default     = false
}

variable "api_lambda_zip_path" {
  description = "Path to the packaged backend Lambda zip file"
  type        = string
  default     = "../../backend/api/api_lambda.zip"
}

variable "api_lambda_timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 30
}

variable "api_lambda_memory_size" {
  description = "Lambda memory size in MB"
  type        = number
  default     = 1024
}

variable "api_lambda_environment" {
  description = "Extra environment variables passed to the backend Lambda"
  type        = map(string)
  default     = {}
}

variable "additional_cors_origins" {
  description = "Extra frontend origins allowed by API Gateway and Lambda CORS"
  type        = list(string)
  default     = []
}

variable "clerk_jwks_url" {
  description = "Clerk JWKS URL used by the backend Lambda"
  type        = string
  default     = ""
}

variable "clerk_issuer" {
  description = "Clerk issuer used by the backend Lambda"
  type        = string
  default     = ""
}

variable "openai_api_key" {
  description = "OpenAI API key for Lambda environment"
  type        = string
  default     = ""
  sensitive   = true
}

variable "openai_model" {
  description = "OpenAI model for Lambda environment"
  type        = string
  default     = "gpt-5-nano"
}

variable "resend_api_key" {
  description = "Resend API key for Lambda email notifications"
  type        = string
  default     = ""
  sensitive   = true
}

variable "resend_from_email" {
  description = "Sender email address for Resend notifications"
  type        = string
  default     = "onboarding@resend.dev"
}

variable "dynamodb_table_name" {
  description = "DynamoDB table name used by the backend Lambda"
  type        = string
  default     = "supplychain-ai-workspaces"
}
