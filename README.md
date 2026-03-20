# AWS S3 Static Website Hosting with Terraform

This Terraform project deploys a **static frontend website** to an **Amazon S3 bucket** configured for **static website hosting**.

It keeps the setup simple and low cost:
- No EC2
- No Amplify
- No RDS
- No CloudFront
- No backend services

## What this project creates

- One S3 bucket for your website files
- S3 static website hosting configuration
- A public-read bucket policy for website assets
- Terraform-managed uploads for **all files inside `./website`**
- Outputs for the website endpoint URL after deployment

## Project structure

```text
.
├── main.tf
├── outputs.tf
├── providers.tf
├── README.md
├── terraform.tfvars.example
├── variables.tf
└── website/
    ├── index.html
    ├── 404.html
    ├── css/
    ├── js/
    └── images/
```

## Where to place your existing website files

Put your existing static site files inside the local `./website` folder.

Example:

```text
website/
├── index.html
├── 404.html
├── css/
│   └── styles.css
├── js/
│   └── app.js
└── images/
    └── logo.png
```

Terraform uses `fileset()` together with `aws_s3_object` resources to upload every file in `./website` while preserving subfolders such as:
- `css/`
- `js/`
- `images/`
- any other nested folders you add

## Bucket naming guidance

Your S3 bucket name should:
- be **globally unique across all AWS accounts**
- use only lowercase letters, numbers, and hyphens
- avoid spaces and uppercase letters
- be easy to recognize

Good example:

```text
my-portfolio-site-2026-abc123
```

> **Important:** S3 bucket names are globally unique in AWS. If someone else already uses the name you choose, `terraform apply` will fail and you must pick another name.

## Variables used by this project

The Terraform configuration uses these variables:
- `aws_region`
- `bucket_name`
- `index_document`
- `error_document`

## Before you deploy

### 1. Make sure your website files exist

Create a `website/` folder in this project if it does not already exist, and place your HTML/CSS/JS/image files inside it.

At minimum, you should normally have:
- `website/index.html`
- `website/404.html`

### 2. Configure AWS credentials

Terraform will use your AWS credentials from the normal AWS provider sources, such as:
- `aws configure`
- environment variables like `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
- an attached IAM role

### 3. Copy the example variables file

Run this command:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Then edit `terraform.tfvars` and set your own globally unique bucket name.

Example:

```hcl
aws_region     = "us-east-1"
bucket_name    = "my-portfolio-site-2026-abc123"
index_document = "index.html"
error_document = "404.html"
```

## Exact deployment commands

### Terraform init

```bash
terraform init
```

### Terraform plan

```bash
terraform plan
```

### Terraform apply

```bash
terraform apply
```

### Terraform destroy

```bash
terraform destroy
```

## Recommended first-time workflow

Run the commands in this order:

```bash
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

After Terraform finishes, get the website URL with:

```bash
terraform output website_url
```

## How file uploads work

This project uploads **all files under `./website`** into the S3 bucket.

Important details:
- Folder structure is preserved automatically
- Common content types are set for:
  - `.html`
  - `.css`
  - `.js`
  - `.png`
  - `.jpg`
  - `.jpeg`
  - `.gif`
  - `.svg`
  - `.webp`
- Unknown file types default to `application/octet-stream`

## S3 static website limitations

S3 static website hosting is simple and inexpensive, but it has a few limitations:

1. **HTTP only on the website endpoint**  
   The native S3 website endpoint does not provide HTTPS by itself.

2. **No backend code**  
   You cannot run server-side code, APIs, databases, or application logic in S3 static hosting.

3. **Limited routing and rewrites**  
   S3 supports index and error documents, but it does not provide full rewrite rules like a traditional web server.

4. **Bucket must be public for direct website hosting**  
   Because this setup does not use CloudFront, the website files are served from a public S3 bucket policy.

## If your site uses client-side routing

If you are deploying a single-page app that uses client-side routing, such as:
- React Router
- Vue Router
- Angular routes

then a direct request to a route like `/about` or `/dashboard/settings` may return an S3 404 error.

### Extra change needed for client-side routing

Set the S3 error document to your main page so unknown routes fall back to the app entry point:

```hcl
error_document = "index.html"
```

That lets your frontend router handle the route after the page loads.

## Clean up resources

To remove everything created by Terraform, run:

```bash
terraform destroy
```

Terraform will delete the bucket and the uploaded website files it manages.
