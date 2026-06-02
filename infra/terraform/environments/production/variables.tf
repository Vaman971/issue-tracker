variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment name"
  type        = string
  default     = "production"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "kubernetes_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.30"
}

variable "node_instance_type" {
  description = "EC2 instance type for EKS worker nodes"
  type        = string
  default     = "c6i.xlarge"
}

variable "node_min_size" {
  description = "Minimum number of worker nodes"
  type        = number
  default     = 3
}

variable "node_max_size" {
  description = "Maximum number of worker nodes (supports peak 10K+ RPS)"
  type        = number
  default     = 15
}

variable "node_desired_size" {
  description = "Initial desired number of worker nodes"
  type        = number
  default     = 3
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.r6g.large"
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "issuetracker"
}

variable "db_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "issueadmin"
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.r6g.large"
}

variable "redis_num_shards" {
  description = "Number of Redis cluster shards"
  type        = number
  default     = 3
}

variable "github_org" {
  description = "GitHub organisation or user name (for OIDC trust)"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name (for OIDC trust)"
  type        = string
  default     = "issueTraker"
}

variable "s3_uploads_bucket" {
  description = "S3 bucket name used for file uploads"
  type        = string
}

variable "acm_certificate_arn" {
  description = "ARN of the ACM certificate for HTTPS on the ALB"
  type        = string
}
