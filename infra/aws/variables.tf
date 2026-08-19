variable "region" {
  type        = string
  description = "AWS region for all resources."
  default     = "ap-south-1"
}

variable "instance_hostname" {
  type        = string
  description = "Hostname assigned to the EC2 instance."
  default     = "thumbgen"
}

variable "instance_size" {
  type        = string
  description = "EC2 instance type."
  default     = "t3.micro"
}

variable "bucket_prefix" {
  type        = string
  description = "Prefix for the S3 bucket names (account id suffix appended for global uniqueness)."
  default     = "thumbgen"
}

variable "ssh_public_key_path" {
  type        = string
  description = "Absolute path to the SSH public key used for the EC2 key pair. No default on purpose: file() does NOT expand ~."
}

variable "ssh_private_key_path" {
  type        = string
  description = "Absolute path to the matching SSH private key, used by Ansible/GitHub Actions to reach the instance."
}

variable "domain" {
  type        = string
  description = "Public domain served by Caddy. Empty = use the instance public IP (bare HTTP)."
  default     = ""
}
