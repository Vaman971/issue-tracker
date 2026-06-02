variable "name"             { type = string }
variable "cluster_name"     { type = string }
variable "aws_account_id"   { type = string }
variable "aws_region"       { type = string }
variable "github_org"       { type = string }
variable "github_repo"      { type = string }
variable "oidc_provider_arn" { type = string }
variable "oidc_provider_url" { type = string }
variable "s3_bucket_arn"    { type = string }

variable "tags" {
  type    = map(string)
  default = {}
}
