variable "name" {
  type = string
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "cluster_name" {
  type = string
}

variable "single_nat_gateway" {
  description = "Use one NAT gateway instead of one per AZ (saves cost, reduces HA)"
  type        = bool
  default     = false
}

variable "tags" {
  type    = map(string)
  default = {}
}
