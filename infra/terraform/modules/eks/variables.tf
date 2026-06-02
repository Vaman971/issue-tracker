variable "name"         { type = string }
variable "cluster_name" { type = string }
variable "vpc_id"       { type = string }
variable "aws_region"   { type = string }
variable "aws_account_id" { type = string }

variable "kubernetes_version" {
  type    = string
  default = "1.30"
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "node_instance_type" {
  type    = string
  default = "c6i.xlarge"
}

variable "node_min_size"     { type = number; default = 3 }
variable "node_max_size"     { type = number; default = 15 }
variable "node_desired_size" { type = number; default = 3 }

variable "lb_controller_role_arn"      { type = string }
variable "cluster_autoscaler_role_arn" { type = string }
variable "external_secrets_role_arn"   { type = string }

variable "tags" {
  type    = map(string)
  default = {}
}
