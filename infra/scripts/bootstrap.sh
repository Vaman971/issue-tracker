#!/usr/bin/env bash
# bootstrap.sh — one-time setup before running terraform apply
# Run this once from a machine with AWS admin credentials.
set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-south-1}"
TF_STATE_BUCKET="issue-tracker-terraform-state"
TF_LOCK_TABLE="issue-tracker-terraform-locks"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "==> Bootstrap: account=${ACCOUNT_ID}, region=${AWS_REGION}"

# ── 1. S3 bucket for Terraform state ────────────────────────────────────────
if ! aws s3api head-bucket --bucket "${TF_STATE_BUCKET}" 2>/dev/null; then
  echo "Creating Terraform state bucket: ${TF_STATE_BUCKET}"
  aws s3api create-bucket \
    --bucket "${TF_STATE_BUCKET}" \
    --region "${AWS_REGION}" \
    --create-bucket-configuration LocationConstraint="${AWS_REGION}"
  aws s3api put-bucket-versioning \
    --bucket "${TF_STATE_BUCKET}" \
    --versioning-configuration Status=Enabled
  aws s3api put-bucket-encryption \
    --bucket "${TF_STATE_BUCKET}" \
    --server-side-encryption-configuration '{
      "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
    }'
  aws s3api put-public-access-block \
    --bucket "${TF_STATE_BUCKET}" \
    --public-access-block-configuration \
      "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
  echo "  ✓ State bucket created"
else
  echo "  ✓ State bucket already exists"
fi

# ── 2. DynamoDB table for Terraform state locking ───────────────────────────
if ! aws dynamodb describe-table --table-name "${TF_LOCK_TABLE}" \
     --region "${AWS_REGION}" 2>/dev/null; then
  echo "Creating Terraform lock table: ${TF_LOCK_TABLE}"
  aws dynamodb create-table \
    --table-name "${TF_LOCK_TABLE}" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "${AWS_REGION}"
  aws dynamodb wait table-exists \
    --table-name "${TF_LOCK_TABLE}" \
    --region "${AWS_REGION}"
  echo "  ✓ Lock table created"
else
  echo "  ✓ Lock table already exists"
fi

# ── 3. Create AWS Secrets Manager secret with placeholder values ─────────────
SECRET_NAME="issue-tracker/production"
if ! aws secretsmanager describe-secret \
     --secret-id "${SECRET_NAME}" \
     --region "${AWS_REGION}" 2>/dev/null; then
  echo "Creating Secrets Manager secret: ${SECRET_NAME}"
  aws secretsmanager create-secret \
    --name "${SECRET_NAME}" \
    --region "${AWS_REGION}" \
    --description "Runtime secrets for the Issue Tracker application" \
    --secret-string '{
      "DATABASE_URL":           "REPLACE_ME",
      "REDIS_URL":              "REPLACE_ME",
      "JWT_SECRET_KEY":         "REPLACE_ME_WITH_64_CHAR_RANDOM_STRING",
      "JWT_REFRESH_SECRET_KEY": "REPLACE_ME_WITH_ANOTHER_64_CHAR_RANDOM_STRING",
      "S3_BUCKET_NAME":         "issue-tracker-uploads-prod",
      "SMTP_HOST":              "smtp.example.com",
      "SMTP_USERNAME":          "apikey",
      "SMTP_PASSWORD":          "REPLACE_ME",
      "NEXT_PUBLIC_API_URL":    "https://yourdomain.com"
    }'
  echo "  ✓ Secret created — update values at:"
  echo "    https://${AWS_REGION}.console.aws.amazon.com/secretsmanager/secret?name=${SECRET_NAME}&region=${AWS_REGION}"
else
  echo "  ✓ Secret already exists"
fi

echo ""
echo "==> Bootstrap complete."
echo ""
echo "Next steps:"
echo "  1. Copy infra/terraform/environments/production/terraform.tfvars.example"
echo "     to terraform.tfvars and fill in all values."
echo "  2. Update the AWS Secrets Manager secret '${SECRET_NAME}' with real values."
echo "  3. Run: cd infra/terraform/environments/production && terraform init && terraform apply"
echo "  4. After apply, run infra/scripts/kubeconfig.sh to configure kubectl."
echo "  5. kubectl apply -f infra/kubernetes/namespace.yaml"
echo "  6. kubectl apply -f infra/kubernetes/secrets/external-secrets.yaml"
echo "  7. Apply remaining manifests or push to main to trigger the pipeline."
echo ""
echo "  Add these secrets to GitHub (Settings → Secrets → Actions):"
echo "    AWS_GITHUB_ACTIONS_ROLE_ARN  — from: terraform output github_actions_role_arn"
echo "    NEXT_PUBLIC_API_URL          — e.g. https://yourdomain.com"
