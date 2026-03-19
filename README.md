# Terraform AWS S3 Static Website Deployment

## Overview

This project deploys a static website to AWS S3 using Terraform. It includes:
- S3 bucket for static website hosting
- Public read policy for website objects
- Website hosting configuration (index + error documents)
- Upload of all files from local `./website` folder preserving folder structure
- Output of website endpoint URL

## File structure

```
.
├── README.md
├── providers.tf
├── main.tf
├── variables.tf
├── outputs.tf
├── terraform.tfvars.example
└── website/
    ├── index.html
    ├── 404.html
    ├── css/
    ├── js/
    ├── images/
    └── ...
```

## Place your website files

Put your existing HTML/CSS/JS/images under `./website`:
- `website/index.html`
- `website/404.html` (or another error page)
- `website/css/style.css`
- `website/js/app.js`
- `website/images/logo.png`

Terraform preserves subfolders with `aws_s3_bucket_object` for each file.

## Bucket naming

- Must be globally unique across all AWS accounts.
- Lowercase letters, numbers, hyphens (`-`), and periods (`.`) only.
- No uppercase, no underscores, no spaces.
- Example: `my-static-website-2026-abcde`

## Deploy process

1. Copy example var file:

```bash
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars and set a unique bucket_name
```

2. Initialize Terraform:

```bash
terraform init
```

3. Review plan:

```bash
terraform plan -out tfplan
```

4. Apply:

```bash
terraform apply tfplan
```

5. Get endpoint:

```bash
terraform output website_url
```

6. Clean up:

```bash
terraform destroy -auto-approve
```

## Notes

- S3 static hosting is HTTP only. For HTTPS, add CloudFront in a later step (not included here).
- `bucket_name` must be unique globally; if conflicting, Terraform apply fails.
- File uploads set content types for common extensions; unknown extensions fall back to `application/octet-stream`.

## Client-side routing (SPA) note

If your site uses client-side routing (React Router, Vue Router, etc.) and deep URLs like `/app/page`, then S3 returns 404 for non-root paths.

Two options:
- Simple: set `error_document = "index.html"` so any unknown route returns index and router handles path.
- Robust: use CloudFront + Lambda@Edge or AWS CloudFront Function to rewrite all unmatched requests to `index.html`.

## Limitations of S3 static hosting

- No server-side rendering or backend logic.
- No built-in HTTPS on static website endpoint (only via CloudFront).
- Limited redirect/rewrite support (basic index/error).
- Large scale should consider CloudFront + caching.
