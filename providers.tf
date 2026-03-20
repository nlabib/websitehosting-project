terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# Configure the AWS provider.
# Terraform reads your AWS credentials from the standard AWS CLI locations,
# environment variables, or IAM role credentials.
provider "aws" {
  region = var.aws_region
}
