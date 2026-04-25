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

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  name_prefix = var.project_name
  bucket_name = var.frontend_bucket_name != "" ? var.frontend_bucket_name : "${local.name_prefix}-frontend-${data.aws_caller_identity.current.account_id}"

  common_tags = {
    Project   = var.project_name
    Part      = "4_frontend"
    ManagedBy = "terraform"
  }
}

resource "aws_s3_bucket" "frontend" {
  bucket        = local.bucket_name
  force_destroy = var.force_destroy_frontend_bucket
  tags          = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html"
  }
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${local.name_prefix}-frontend-oac"
  description                       = "Origin access control for ${local.name_prefix} frontend bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${local.name_prefix} frontend CDN"
  default_root_object = "index.html"
  price_class         = var.cloudfront_price_class
  aliases             = var.frontend_aliases
  tags                = local.common_tags

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "s3-${aws_s3_bucket.frontend.id}"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-${aws_s3_bucket.frontend.id}"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = true

      cookies {
        forward = "all"
      }
    }
  }

  ordered_cache_behavior {
    path_pattern           = "_next/static/*"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-${aws_s3_bucket.frontend.id}"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = false

      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 86400
    max_ttl     = 31536000
  }

  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn            = var.acm_certificate_arn != "" ? var.acm_certificate_arn : null
    cloudfront_default_certificate = var.acm_certificate_arn == ""
    ssl_support_method             = var.acm_certificate_arn != "" ? "sni-only" : null
    minimum_protocol_version       = var.acm_certificate_arn != "" ? "TLSv1.2_2021" : null
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontRead"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.frontend.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.frontend.arn
          }
        }
      }
    ]
  })
}

resource "aws_iam_role" "api_lambda" {
  count = var.enable_api_lambda ? 1 : 0
  name  = "${local.name_prefix}-api-lambda-role"
  tags  = local.common_tags

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "api_lambda_basic" {
  count      = var.enable_api_lambda ? 1 : 0
  role       = aws_iam_role.api_lambda[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "api_lambda_dynamodb" {
  count = var.enable_api_lambda ? 1 : 0
  name  = "${local.name_prefix}-api-lambda-dynamodb"
  role  = aws_iam_role.api_lambda[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:DescribeTable",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
        ]
        Resource = "arn:aws:dynamodb:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:table/${var.dynamodb_table_name}"
      }
    ]
  })
}

resource "aws_lambda_function" "api" {
  count            = var.enable_api_lambda ? 1 : 0
  filename         = var.api_lambda_zip_path
  function_name    = "${local.name_prefix}-api"
  role             = aws_iam_role.api_lambda[0].arn
  handler          = "lambda_handler.handler"
  source_code_hash = filebase64sha256(var.api_lambda_zip_path)
  runtime          = "python3.12"
  timeout          = var.api_lambda_timeout
  memory_size      = var.api_lambda_memory_size
  architectures    = ["x86_64"]
  tags             = local.common_tags
  publish          = true

  environment {
    variables = merge(
      {
        CORS_ORIGINS = join(
          ",",
          concat(
            [
              "http://localhost:3000",
              "http://127.0.0.1:3000",
              "https://${aws_cloudfront_distribution.frontend.domain_name}",
            ],
            var.additional_cors_origins,
          ),
        )
        DEFAULT_AWS_REGION   = var.aws_region
        DYNAMODB_TABLE_NAME  = var.dynamodb_table_name
        DYNAMODB_AUTO_CREATE = "false"
        CLERK_JWKS_URL       = var.clerk_jwks_url
        CLERK_ISSUER         = var.clerk_issuer
        OPENAI_API_KEY       = var.openai_api_key
        OPENAI_MODEL         = var.openai_model
        RESEND_API_KEY       = var.resend_api_key
        RESEND_FROM_EMAIL    = var.resend_from_email
      },
      var.api_lambda_environment,
    )
  }
}

resource "aws_lambda_alias" "api_live" {
  count            = var.enable_api_lambda ? 1 : 0
  name             = "live"
  description      = "Stable alias for API Gateway and provisioned concurrency"
  function_name    = aws_lambda_function.api[0].function_name
  function_version = aws_lambda_function.api[0].version
}

resource "aws_lambda_provisioned_concurrency_config" "api_live" {
  count = var.enable_api_lambda && var.api_lambda_provisioned_concurrency > 0 ? 1 : 0

  function_name                     = aws_lambda_function.api[0].function_name
  qualifier                         = aws_lambda_alias.api_live[0].name
  provisioned_concurrent_executions = var.api_lambda_provisioned_concurrency
}

resource "aws_apigatewayv2_api" "main" {
  count         = var.enable_api_lambda ? 1 : 0
  name          = "${local.name_prefix}-api-gateway"
  protocol_type = "HTTP"
  tags          = local.common_tags

  cors_configuration {
    allow_credentials = false
    allow_headers     = ["authorization", "content-type", "x-actor-email", "x-amz-date", "x-api-key", "x-amz-security-token"]
    allow_methods     = ["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"]
    allow_origins = concat(
      ["http://localhost:3000", "http://127.0.0.1:3000", "https://${aws_cloudfront_distribution.frontend.domain_name}"],
      var.additional_cors_origins,
    )
    max_age = 300
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  count                  = var.enable_api_lambda ? 1 : 0
  api_id                 = aws_apigatewayv2_api.main[0].id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_alias.api_live[0].invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "proxy" {
  count     = var.enable_api_lambda ? 1 : 0
  api_id    = aws_apigatewayv2_api.main[0].id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda[0].id}"
}

resource "aws_apigatewayv2_route" "root" {
  count     = var.enable_api_lambda ? 1 : 0
  api_id    = aws_apigatewayv2_api.main[0].id
  route_key = "ANY /"
  target    = "integrations/${aws_apigatewayv2_integration.lambda[0].id}"
}

resource "aws_apigatewayv2_stage" "default" {
  count       = var.enable_api_lambda ? 1 : 0
  api_id      = aws_apigatewayv2_api.main[0].id
  name        = "$default"
  auto_deploy = true
  tags        = local.common_tags
}

resource "aws_lambda_permission" "api_gateway" {
  count         = var.enable_api_lambda ? 1 : 0
  statement_id  = "AllowExecutionFromApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_alias.api_live[0].arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main[0].execution_arn}/*/*"
}
