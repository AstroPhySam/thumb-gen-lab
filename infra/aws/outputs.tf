output "instance_id" {
  value = aws_instance.app.id
}

output "instance_public_ip" {
  value = aws_instance.app.public_ip
}

output "ssh_command" {
  value = "ssh -i ${var.ssh_private_key_path} root@${aws_instance.app.public_ip}"
}

output "ecr_registry_url" {
  value = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com"
}

output "originals_bucket" {
  value = aws_s3_bucket.originals.id
}

output "thumbnails_bucket" {
  value = aws_s3_bucket.thumbnails.id
}

output "gh_actions_role_arn" {
  value = aws_iam_role.gh_actions.arn
}

output "app_iam_access_key" {
  value     = aws_iam_access_key.thumbgen_app.id
  sensitive = true
}

output "app_iam_secret" {
  value     = aws_iam_access_key.thumbgen_app.secret
  sensitive = true
}
