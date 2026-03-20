variable "aws_region" {
  description = "AWS region where the S3 static website bucket will be created."
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "Globally unique name for the S3 bucket that will host the website."
  type        = string
}

variable "index_document" {
  description = "Default page that S3 returns for the site root."
  type        = string
  default     = "index.html"
}

variable "error_document" {
  description = "Error page that S3 returns for missing pages or website errors."
  type        = string
  default     = "404.html"
}

variable "jwt_secret" {
  description = "Secret key used to sign and verify JWTs. Keep this private."
  type        = string
  sensitive   = true
}
