variable "name"           { type = string }
variable "vpc_id"         { type = string }
variable "subnet_ids"     { type = list(string) }
variable "eks_node_sg_id" { type = string }

variable "node_type" {
  type    = string
  default = "cache.r6g.large"
}

variable "num_shards" {
  description = "Number of Redis cluster shards (each shard gets 1 replica)"
  type        = number
  default     = 3
}

variable "tags" {
  type    = map(string)
  default = {}
}
