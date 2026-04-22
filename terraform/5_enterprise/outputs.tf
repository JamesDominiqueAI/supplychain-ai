output "dashboard_name" {
  description = "CloudWatch dashboard name"
  value       = aws_cloudwatch_dashboard.operations.dashboard_name
}

output "sns_topic_arn" {
  description = "SNS topic used for enterprise alarms"
  value       = aws_sns_topic.enterprise_alerts.arn
}

output "configured_alarm_email" {
  description = "Email currently configured for SNS subscription"
  value       = var.alarm_email
}
