output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS API server endpoint"
  value       = module.eks.cluster_endpoint
}

output "ecr_backend_url" {
  description = "ECR URL for the backend image"
  value       = module.ecr.backend_repository_url
}

output "ecr_frontend_url" {
  description = "ECR URL for the frontend image"
  value       = module.ecr.frontend_repository_url
}

output "rds_endpoint" {
  description = "RDS writer endpoint"
  value       = module.rds.endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "ElastiCache configuration endpoint"
  value       = module.elasticache.configuration_endpoint
  sensitive   = true
}

output "github_actions_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC — add as AWS_GITHUB_ACTIONS_ROLE_ARN secret"
  value       = module.iam.github_actions_role_arn
}

output "backend_irsa_role_arn" {
  description = "IAM role ARN for the backend pod service account"
  value       = module.iam.backend_role_arn
}
