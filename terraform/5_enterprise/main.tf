terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  name_prefix = var.project_name

  common_tags = {
    Project   = var.project_name
    Part      = "5_enterprise"
    ManagedBy = "terraform"
  }

  dashboard_widgets = concat(
    [
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 3
        properties = {
          markdown = "## SupplyChain AI Operations\nThis dashboard follows the alex deployment model: CDN delivery, alarms, and operational visibility."
        }
      }
    ],
    var.cloudfront_distribution_id != "" ? [
      {
        type   = "metric"
        x      = 0
        y      = 3
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/CloudFront", "Requests", "DistributionId", var.cloudfront_distribution_id, "Region", "Global", { stat = "Sum", label = "Requests" }],
            ["AWS/CloudFront", "4xxErrorRate", "DistributionId", var.cloudfront_distribution_id, "Region", "Global", { stat = "Average", label = "4xx %" }],
            ["AWS/CloudFront", "5xxErrorRate", "DistributionId", var.cloudfront_distribution_id, "Region", "Global", { stat = "Average", label = "5xx %" }]
          ]
          region = "us-east-1"
          title  = "CloudFront Traffic And Errors"
          view   = "timeSeries"
          period = 300
        }
      }
    ] : [],
    var.api_gateway_id != "" ? [
      {
        type   = "metric"
        x      = 12
        y      = 3
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/ApiGateway", "Count", "ApiId", var.api_gateway_id, { stat = "Sum", label = "Requests" }],
            ["AWS/ApiGateway", "4xx", "ApiId", var.api_gateway_id, { stat = "Sum", label = "4xx" }],
            ["AWS/ApiGateway", "5xx", "ApiId", var.api_gateway_id, { stat = "Sum", label = "5xx" }],
            ["AWS/ApiGateway", "Latency", "ApiId", var.api_gateway_id, { stat = "Average", label = "Latency" }]
          ]
          region = var.aws_region
          title  = "API Gateway Health"
          view   = "timeSeries"
          period = 300
        }
      }
    ] : [],
    var.lambda_function_name != "" ? [
      {
        type   = "metric"
        x      = 0
        y      = 9
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", var.lambda_function_name, { stat = "Sum", label = "Invocations" }],
            ["AWS/Lambda", "Errors", "FunctionName", var.lambda_function_name, { stat = "Sum", label = "Errors" }],
            ["AWS/Lambda", "Duration", "FunctionName", var.lambda_function_name, { stat = "Average", label = "Duration" }],
            ["AWS/Lambda", "Throttles", "FunctionName", var.lambda_function_name, { stat = "Sum", label = "Throttles" }]
          ]
          region = var.aws_region
          title  = "Backend Lambda Health"
          view   = "timeSeries"
          period = 300
        }
      }
    ] : []
  )
}

resource "aws_sns_topic" "enterprise_alerts" {
  name = "${local.name_prefix}-enterprise-alerts"
  tags = local.common_tags
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alarm_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.enterprise_alerts.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

resource "aws_cloudwatch_dashboard" "operations" {
  dashboard_name = "${local.name_prefix}-operations"
  dashboard_body = jsonencode({ widgets = local.dashboard_widgets })
}

resource "aws_cloudwatch_metric_alarm" "cloudfront_5xx" {
  count               = var.cloudfront_distribution_id != "" ? 1 : 0
  alarm_name          = "${local.name_prefix}-cloudfront-5xx"
  alarm_description   = "CloudFront 5xx error rate is elevated"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "5xxErrorRate"
  namespace           = "AWS/CloudFront"
  period              = 300
  statistic           = "Average"
  threshold           = var.cloudfront_5xx_alarm_threshold
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.enterprise_alerts.arn]
  ok_actions          = [aws_sns_topic.enterprise_alerts.arn]

  dimensions = {
    DistributionId = var.cloudfront_distribution_id
    Region         = "Global"
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  count               = var.lambda_function_name != "" ? 1 : 0
  alarm_name          = "${local.name_prefix}-lambda-errors"
  alarm_description   = "Backend Lambda is returning errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = var.lambda_error_alarm_threshold
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.enterprise_alerts.arn]
  ok_actions          = [aws_sns_topic.enterprise_alerts.arn]

  dimensions = {
    FunctionName = var.lambda_function_name
  }

  tags = local.common_tags
}
