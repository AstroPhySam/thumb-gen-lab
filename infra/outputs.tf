output "instance_id" {
  value = civo_instance.app.id
}

output "instance_public_ip" {
  value = civo_instance.app.public_ip
}

output "instance_hostname" {
  value = civo_instance.app.hostname
}

output "instance_size" {
  value = civo_instance.app.size
}

output "ssh_command" {
  value = "ssh -i ${var.ssh_private_key_path} root@${civo_instance.app.public_ip}"
}
