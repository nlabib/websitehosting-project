resource "aws_s3_bucket" "designs" {
  bucket = "cloudsev-designs"
  tags   = { Project = "cloudsev", ManagedBy = "Terraform" }
}

resource "aws_s3_bucket_public_access_block" "designs" {
  bucket                  = aws_s3_bucket.designs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_cors_configuration" "designs" {
  bucket = aws_s3_bucket.designs.id

  cors_rule {
    allowed_methods = ["PUT"]
    allowed_origins = ["*"]
    allowed_headers = ["*"]
    max_age_seconds = 3000
  }
}
