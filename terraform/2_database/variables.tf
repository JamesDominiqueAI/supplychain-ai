variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "supplychain-ai"
}

variable "dynamodb_table_name" {
  type    = string
  default = ""
}

variable "enable_point_in_time_recovery" {
  type    = bool
  default = true
}
