output "configuration_endpoint" {
  description = "Cluster mode configuration endpoint (use this for the Redis URL)"
  value       = aws_elasticache_replication_group.main.configuration_endpoint_address
  sensitive   = true
}

output "auth_token_secret_arn" {
  description = "Secrets Manager ARN holding the Redis AUTH token"
  value       = aws_secretsmanager_secret.redis_auth.arn
}
