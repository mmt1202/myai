terraform {
  required_version = ">= 1.6.0"
}

variable "environment" {
  type    = string
  default = "staging"
}

variable "region" {
  type    = string
  default = "us-west-2"
}

variable "app_name" {
  type    = string
  default = "myai-foundation"
}

output "deployment_profile" {
  value = {
    app_name    = var.app_name
    environment = var.environment
    region      = var.region
    resources   = ["network", "database", "object_storage", "queue", "secrets", "cdn", "observability"]
  }
}
