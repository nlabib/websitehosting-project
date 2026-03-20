# Local values keep the main resources easier to read.
locals {
  # This project expects your website source files to live in ./website.
  website_root = "${path.module}/website"

  # Collect every file under ./website and preserve nested folders such as
  # css/, js/, images/, and any other subdirectories.
  website_files = fileset(local.website_root, "**")

  # Map common file extensions to the correct HTTP content type so browsers
  # render assets properly when they are served from S3.
  mime_types = {
    html = "text/html"
    css  = "text/css"
    js   = "application/javascript"
    png  = "image/png"
    jpg  = "image/jpeg"
    jpeg = "image/jpeg"
    gif  = "image/gif"
    svg  = "image/svg+xml"
    webp = "image/webp"
  }
}

# Create the S3 bucket that will store the static website files.
resource "aws_s3_bucket" "static_site" {
  bucket = var.bucket_name

  tags = {
    Name        = var.bucket_name
    Project     = "static-website-hosting"
    ManagedBy   = "Terraform"
  }
}

# Explicitly allow public bucket policies for this bucket.
# S3 static website hosting needs public read access when you are not using
# CloudFront or another private origin setup.
resource "aws_s3_bucket_public_access_block" "static_site" {
  bucket = aws_s3_bucket.static_site.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# Enable static website hosting and define the default index and error pages.
resource "aws_s3_bucket_website_configuration" "static_site" {
  bucket = aws_s3_bucket.static_site.id

  index_document {
    suffix = var.index_document
  }

  error_document {
    key = var.error_document
  }
}

# Build a simple policy that allows anyone on the internet to read the website
# files. This is required for direct S3 static website hosting.
data "aws_iam_policy_document" "public_read" {
  statement {
    sid    = "PublicReadGetObject"
    effect = "Allow"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:GetObject"]

    resources = [
      "${aws_s3_bucket.static_site.arn}/*",
    ]
  }
}

# Attach the public-read bucket policy.
resource "aws_s3_bucket_policy" "public_read" {
  bucket = aws_s3_bucket.static_site.id
  policy = data.aws_iam_policy_document.public_read.json

  depends_on = [aws_s3_bucket_public_access_block.static_site]
}

# Upload every file from ./website into the bucket.
# The object key matches the relative path so folder structure is preserved.
resource "aws_s3_object" "website_files" {
  for_each = { for file in local.website_files : file => file }

  bucket = aws_s3_bucket.static_site.id
  key    = each.value
  source = "${local.website_root}/${each.value}"

  # Re-upload the object only when the file contents actually change.
  etag = filemd5("${local.website_root}/${each.value}")

  # Assign the proper content type based on the file extension.
  content_type = lookup(
    local.mime_types,
    lower(element(reverse(split(".", each.value)), 0)),
    "application/octet-stream"
  )
}
