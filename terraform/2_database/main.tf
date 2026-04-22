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
  table_name = var.dynamodb_table_name != "" ? var.dynamodb_table_name : "${var.project_name}-workspaces"
}

resource "aws_dynamodb_table" "workspace" {
  name         = local.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "owner_user_id"

  attribute {
    name = "owner_user_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Project   = var.project_name
    Part      = "2_database"
    ManagedBy = "terraform"
  }
}
