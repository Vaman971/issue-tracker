variable "name"           { type = string }
variable "vpc_id"         { type = string }
variable "subnet_ids"     { type = list(string) }
variable "eks_node_sg_id" { type = string }

variable "db_instance_class" {
  type    = string
  default = "db.r6g.large"
}

variable "db_name" {
  type    = string
  default = "issuetracker"
}

variable "db_username" {
  type    = string
  default = "issueadmin"
}

variable "tags" {
  type    = map(string)
  default = {}
}
