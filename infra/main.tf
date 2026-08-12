data "civo_disk_image" "ubuntu" {
  filter {
    key      = "name"
    values   = [var.disk_image_name]
    match_by = "re"
  }
}

resource "civo_ssh_key" "deploy" {
  name       = "thumbgen-deploy"
  public_key = file(var.ssh_public_key_path)
}

resource "civo_firewall" "web" {
  name                 = "thumbgen-web"
  create_default_rules = false

  ingress_rule {
    label      = "ssh"
    protocol   = "tcp"
    port_range = "22"
    cidr       = ["0.0.0.0/0"]
    action     = "allow"
  }

  ingress_rule {
    label      = "http"
    protocol   = "tcp"
    port_range = "80"
    cidr       = ["0.0.0.0/0"]
    action     = "allow"
  }

  ingress_rule {
    label      = "https"
    protocol   = "tcp"
    port_range = "443"
    cidr       = ["0.0.0.0/0"]
    action     = "allow"
  }

  egress_rule {
    label      = "all-tcp"
    protocol   = "tcp"
    port_range = "1-65535"
    cidr       = ["0.0.0.0/0"]
    action     = "allow"
  }

  egress_rule {
    label      = "all-udp"
    protocol   = "udp"
    port_range = "1-65535"
    cidr       = ["0.0.0.0/0"]
    action     = "allow"
  }
}

resource "civo_instance" "app" {
  hostname     = var.instance_hostname
  size         = var.instance_size
  disk_image   = data.civo_disk_image.ubuntu.diskimages[0].id
  firewall_id  = civo_firewall.web.id
  initial_user = "root"
  sshkey_id    = civo_ssh_key.deploy.id
}
