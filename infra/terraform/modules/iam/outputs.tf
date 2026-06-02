output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}

output "backend_role_arn" {
  value = aws_iam_role.backend.arn
}

output "cluster_autoscaler_role_arn" {
  value = aws_iam_role.cluster_autoscaler.arn
}

output "lb_controller_role_arn" {
  value = aws_iam_role.lb_controller.arn
}

output "external_secrets_role_arn" {
  value = aws_iam_role.external_secrets.arn
}
