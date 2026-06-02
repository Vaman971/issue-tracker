output "endpoint" {
  value     = aws_db_instance.main.endpoint
  sensitive = true
}

output "address" {
  value = aws_db_instance.main.address
}

output "port" {
  value = aws_db_instance.main.port
}

output "db_name" {
  value = aws_db_instance.main.db_name
}

output "username" {
  value = aws_db_instance.main.username
}

output "password_secret_arn" {
  description = "Secrets Manager ARN holding the DB password"
  value       = aws_secretsmanager_secret.db_password.arn
}
