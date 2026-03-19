variable "aws_region" {
  description = "AWS region for static website hosting, e.g. us-east-1"
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "Globally unique S3 bucket name for your static website"
  type        = string
}

variable "index_document" {
  description = "Default index document for S3 website hosting"
  type        = string
  default     = "index.html"
}

variable "error_document" {
  description = "Fallback error document for S3 website hosting"
  type        = string
  default     = "404.html"
}

variable "website_path" {
  description = "Local path to your website static files"
  type        = string
  default     = "website"
}
