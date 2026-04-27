output "frontend_bucket_name" {
  description = "Name of the private S3 bucket that stores the frontend assets"
  value       = aws_s3_bucket.frontend.id
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID for invalidations and monitoring"
  value       = aws_cloudfront_distribution.frontend.id
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "frontend_url" {
  description = "Public URL of the frontend CDN"
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "api_gateway_url" {
  description = "Backend API Gateway URL when enable_api_lambda is true"
  value       = var.enable_api_lambda ? aws_apigatewayv2_api.main[0].api_endpoint : null
}

output "api_gateway_id" {
  description = "Backend API Gateway ID when enable_api_lambda is true"
  value       = var.enable_api_lambda ? aws_apigatewayv2_api.main[0].id : null
}

output "lambda_function_name" {
  description = "Backend Lambda function name when enable_api_lambda is true"
  value       = var.enable_api_lambda ? aws_lambda_function.api[0].function_name : null
}

output "deploy_instructions" {
  description = "Basic steps for uploading a built frontend"
  value       = <<-EOT
    1. Build the frontend for CloudFront:
       cd frontend
       npm run build:static

    2. Upload the static output:
       aws s3 sync out/ s3://${aws_s3_bucket.frontend.id}/ --delete

    3. Invalidate CloudFront:
       aws cloudfront create-invalidation --distribution-id ${aws_cloudfront_distribution.frontend.id} --paths "/*"

    4. If enable_api_lambda is true, package and deploy the backend zip before terraform apply:
       backend/api/api_lambda.zip

    Note:
    This phase deploys the frontend CDN plus optional backend Lambda + API Gateway in the same layer.
  EOT
}
