terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local state for now — can migrate to S3 backend later
  required_version = ">= 1.6.0"
}

provider "aws" {
  region = var.aws_region
}
