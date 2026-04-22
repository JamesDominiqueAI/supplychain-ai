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

variable "alarm_email" {
  description = "Optional email address subscribed to SNS alerts"
  type        = string
  default     = ""
}

variable "cloudfront_distribution_id" {
  description = "CloudFront distribution ID to monitor"
  type        = string
  default     = ""
}

variable "api_gateway_id" {
  description = "HTTP API or REST API identifier to monitor"
  type        = string
  default     = ""
}

variable "lambda_function_name" {
  description = "Backend Lambda function name to monitor"
  type        = string
  default     = ""
}

variable "cloudfront_5xx_alarm_threshold" {
  description = "5xx error rate threshold for CloudFront alarm"
  type        = number
  default     = 1
}

variable "lambda_error_alarm_threshold" {
  description = "Lambda error count threshold per evaluation period"
  type        = number
  default     = 1
}
