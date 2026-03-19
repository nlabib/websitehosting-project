output "bucket_name" {
  description = "Name of the S3 bucket used for website hosting"
  value       = aws_s3_bucket.static_site.bucket
}

output "website_url" {
  description = "S3 website URL"
  value       = aws_s3_bucket.static_site.website_endpoint
}
