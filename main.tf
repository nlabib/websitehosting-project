locals {
  website_files = fileset(var.website_path, "**")
}

resource "aws_s3_bucket" "static_site" {
  bucket = var.bucket_name
  acl    = "public-read"

  website {
    index_document = var.index_document
    error_document = var.error_document
  }

  tags = {
    Name        = "Static Website Bucket"
    Environment = "Dev"
  }
}

resource "aws_s3_bucket_public_access_block" "static_site_block" {
  bucket = aws_s3_bucket.static_site.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

data "aws_iam_policy_document" "public_read_policy" {
  statement {
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    actions = [
      "s3:GetObject",
    ]

    resources = [
      "${aws_s3_bucket.static_site.arn}/*",
    ]
  }
}

resource "aws_s3_bucket_policy" "static_site_policy" {
  bucket = aws_s3_bucket.static_site.id
  policy = data.aws_iam_policy_document.public_read_policy.json
}

resource "aws_s3_bucket_object" "website_objects" {
  for_each = { for file in local.website_files : file => file }

  bucket = aws_s3_bucket.static_site.id
  key    = each.value
  source = "${path.module}/${var.website_path}/${each.value}"
  acl    = "public-read"

  content_type = lookup({
    "html" = "text/html",
    "css"  = "text/css",
    "js"   = "application/javascript",
    "png"  = "image/png",
    "jpg"  = "image/jpeg",
    "jpeg" = "image/jpeg",
    "gif"  = "image/gif",
    "svg"  = "image/svg+xml",
    "webp" = "image/webp",
    "json" = "application/json",
    "pdf"  = "application/pdf",
    "txt"  = "text/plain"
  }, lower(trimspace(split(".", each.value)[length(split(".", each.value)) - 1])), "application/octet-stream")
}
