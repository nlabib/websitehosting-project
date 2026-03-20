output "bucket_name" {
  description = "Name of the S3 bucket hosting the static website."
  value       = aws_s3_bucket.static_site.bucket
}

output "website_endpoint" {
  description = "Regional S3 static website endpoint URL."
  value       = aws_s3_bucket_website_configuration.static_site.website_endpoint
}

output "website_url" {
  description = "Convenient HTTP URL for the hosted website."
  value       = "http://${aws_s3_bucket_website_configuration.static_site.website_endpoint}"
}
