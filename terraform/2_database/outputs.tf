output "dynamodb_table_name" {
  value = aws_dynamodb_table.workspace.name
}

output "dynamodb_table_arn" {
  value = aws_dynamodb_table.workspace.arn
}
