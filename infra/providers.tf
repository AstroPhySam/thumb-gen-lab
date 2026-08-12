terraform {
  required_version = ">= 1.6"

  required_providers {
    civo = {
      source  = "civo/civo"
      version = "~> 1.3"
    }
  }

  backend "s3" {
    bucket = "infrastates"
    key    = "image-thumb-gen-lab/terraform.tfstate"
    region = "MUM1"
    endpoints = {
      s3 = "https://objectstore.mum1.civo.com"
    }
    skip_region_validation      = true
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_s3_checksum            = true
    use_path_style              = true
  }
}

provider "civo" {
  region = var.region
}
