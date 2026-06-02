locals {
  name         = "issue-tracker"
  cluster_name = "${local.name}-${var.environment}"

  common_tags = {
    Project     = local.name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

data "aws_caller_identity" "current" {}

# ── Networking ────────────────────────────────────────────────────────────────
module "vpc" {
  source = "../../modules/vpc"

  name               = local.name
  vpc_cidr           = var.vpc_cidr
  cluster_name       = local.cluster_name
  single_nat_gateway = false
  tags               = local.common_tags
}

# ── S3 bucket for file uploads ────────────────────────────────────────────────
resource "aws_s3_bucket" "uploads" {
  bucket        = var.s3_uploads_bucket
  force_destroy = false
  tags          = local.common_tags
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket                  = aws_s3_bucket.uploads.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

# ── Container registries ─────────────────────────────────────────────────────
module "ecr" {
  source = "../../modules/ecr"

  name = local.name
  tags = local.common_tags
}

# ── IAM roles (OIDC for pods + GitHub Actions) ────────────────────────────────
module "iam" {
  source = "../../modules/iam"

  name              = local.name
  cluster_name      = local.cluster_name
  aws_account_id    = data.aws_caller_identity.current.account_id
  aws_region        = var.aws_region
  github_org        = var.github_org
  github_repo       = var.github_repo
  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_provider_url = module.eks.oidc_provider_url
  s3_bucket_arn     = aws_s3_bucket.uploads.arn
  tags              = local.common_tags
}

# ── EKS cluster + node group + in-cluster tooling ─────────────────────────────
module "eks" {
  source = "../../modules/eks"

  name               = local.name
  cluster_name       = local.cluster_name
  kubernetes_version = var.kubernetes_version
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  aws_region         = var.aws_region
  aws_account_id     = data.aws_caller_identity.current.account_id

  node_instance_type = var.node_instance_type
  node_min_size      = var.node_min_size
  node_max_size      = var.node_max_size
  node_desired_size  = var.node_desired_size

  lb_controller_role_arn      = module.iam.lb_controller_role_arn
  cluster_autoscaler_role_arn = module.iam.cluster_autoscaler_role_arn
  external_secrets_role_arn   = module.iam.external_secrets_role_arn

  tags = local.common_tags
}

# ── EKS access entries ────────────────────────────────────────────────────────
resource "aws_eks_access_entry" "github_actions" {
  cluster_name  = module.eks.cluster_name
  principal_arn = module.iam.github_actions_role_arn
  type          = "STANDARD"
  tags          = local.common_tags
}

resource "aws_eks_access_policy_association" "github_actions" {
  cluster_name  = module.eks.cluster_name
  principal_arn = module.iam.github_actions_role_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.github_actions]
}

# ── Managed PostgreSQL ────────────────────────────────────────────────────────
module "rds" {
  source = "../../modules/rds"

  name           = local.name
  vpc_id         = module.vpc.vpc_id
  subnet_ids     = module.vpc.private_subnet_ids
  eks_node_sg_id = module.eks.node_security_group_id

  db_instance_class = var.db_instance_class
  db_name           = var.db_name
  db_username       = var.db_username

  tags = local.common_tags
}

# ── Managed Redis ─────────────────────────────────────────────────────────────
module "elasticache" {
  source = "../../modules/elasticache"

  name           = local.name
  vpc_id         = module.vpc.vpc_id
  subnet_ids     = module.vpc.private_subnet_ids
  eks_node_sg_id = module.eks.node_security_group_id

  node_type  = var.redis_node_type
  num_shards = var.redis_num_shards

  tags = local.common_tags
}
