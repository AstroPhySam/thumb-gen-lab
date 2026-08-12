variable "region" {
  type        = string
  description = "Civo region for the instance, firewall and object store (must match the object store region)."
  default     = "MUM1"
}

variable "instance_hostname" {
  type        = string
  description = "Hostname assigned to the compute instance."
  default     = "thumbgen"
}

variable "instance_size" {
  type        = string
  description = "Civo instance size."
  default     = "g4s.small"
}

variable "disk_image_name" {
  type        = string
  description = "Disk image name regex matched against Civo's image list."
  default     = "ubuntu-noble"
}

variable "ssh_public_key_path" {
  type        = string
  description = "Absolute path to the SSH public key uploaded to Civo. No default on purpose: file() does NOT expand ~, so set an absolute path in terraform.tfvars (or via -var in CI)."
}

variable "ssh_private_key_path" {
  type        = string
  description = "Absolute path to the matching SSH private key, used by Ansible/GitHub Actions to reach the instance. Same ~ caveat as ssh_public_key_path."
}
