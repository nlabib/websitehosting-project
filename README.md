# AWS S3 Static Website Hosting for `Phase2_Web_Page`

This Terraform project deploys the existing `Phase2_Web_Page` frontend to an Amazon S3 bucket configured for static website hosting.

## What this version fixes

The previous scaffold assumed your site lived in `./website`. Your actual project files are in `./Phase2_Web_Page`, so this version now uploads **that real website folder** directly.

It also makes the site work better as a static deployment by:
- adding a real `index.html` entry page
- adding a `404.html` page
- adding the missing `css/bootstrap.css` stylesheet the HTML already referenced
- removing the placeholder future PHP login action so the login page works as a static navigation page

## Important note about RDS

Your current site is a **static frontend demo**. Amazon S3 can host it successfully by itself.

You do **not** need Amazon RDS unless you want real dynamic features such as:
- user accounts with actual authentication
- saved shopping carts
- persistent order history
- admin-managed product data

If you later want those features, you would normally add:
- a backend application or API
- database tables in Amazon RDS (or another database service)
- authentication and server-side logic

That is **not included** in this Terraform because your current project only contains static HTML and image files.

## Project structure

```text
.
├── main.tf
├── outputs.tf
├── providers.tf
├── README.md
├── terraform.tfvars.example
├── variables.tf
└── Phase2_Web_Page/
    ├── index.html
    ├── 404.html
    ├── Login.html
    ├── HomePage.html
    ├── AccountInfo.html
    ├── Products.html
    ├── UsersPastOrders.html
    ├── css/
    │   └── bootstrap.css
    ├── hat.png
    ├── shirt.png
    └── shoes.png
```

## Files that Terraform uploads

Terraform uploads every file inside `Phase2_Web_Page/` and preserves subfolders such as `css/`.

That means these pages and assets are deployed automatically:
- `Phase2_Web_Page/index.html`
- `Phase2_Web_Page/Login.html`
- `Phase2_Web_Page/HomePage.html`
- `Phase2_Web_Page/AccountInfo.html`
- `Phase2_Web_Page/Products.html`
- `Phase2_Web_Page/UsersPastOrders.html`
- `Phase2_Web_Page/css/bootstrap.css`
- image files like `hat.png`, `shirt.png`, and `shoes.png`

## Bucket naming guidance

Your S3 bucket name must:
- be globally unique across all AWS accounts
- use lowercase letters, numbers, and hyphens
- not contain spaces or uppercase letters

Example:

```text
cloudsev-static-site-2026-demo123
```

> **Warning:** S3 bucket names are globally unique in AWS. If the bucket name is already taken by another AWS account, `terraform apply` will fail and you must choose a different name.

## Variables used

This Terraform project uses these variables:
- `aws_region`
- `bucket_name`
- `index_document`
- `error_document`

Recommended values for this project:

```hcl
aws_region     = "us-east-1"
bucket_name    = "cloudsev-static-site-2026-demo123"
index_document = "index.html"
error_document = "404.html"
```

## AWS credentials

Before running Terraform, make sure your AWS credentials are configured through one of the normal AWS provider methods, such as:
- `aws configure`
- environment variables like `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
- an attached IAM role

## Exact step-by-step commands

### 1. Copy the example variables file

```bash
cp terraform.tfvars.example terraform.tfvars
```

### 2. Edit the variables file

Update `terraform.tfvars` with your real bucket name.

### 3. Initialize Terraform

```bash
terraform init
```

### 4. Review the execution plan

```bash
terraform plan
```

### 5. Deploy the website

```bash
terraform apply
```

### 6. Print the website URL after deployment

```bash
terraform output website_url
```

### 7. Destroy the infrastructure later if needed

```bash
terraform destroy
```

## How the S3 hosting works

This Terraform configuration creates:
- one S3 bucket
- S3 website hosting configuration with `index.html` and `404.html`
- a public bucket policy for website reads
- one Terraform-managed S3 object per local file in `Phase2_Web_Page/`

It also assigns proper content types for common website files:
- `.html`
- `.css`
- `.js`
- `.png`
- `.jpg`
- `.jpeg`
- `.gif`
- `.svg`
- `.webp`

## S3 static website limitations

S3 static website hosting is low cost and simple, but there are important limitations:

1. **HTTP only on the website endpoint**  
   Native S3 website endpoints do not provide HTTPS.

2. **No server-side code**  
   Static S3 hosting cannot process real login forms, save carts, or query a database by itself.

3. **No real database integration in this version**  
   Even though your pages show account and order data, they are still static example values unless you add a backend and database.

4. **Public bucket access is required for direct S3 website hosting**  
   Because this setup does not use CloudFront, the bucket policy must allow public reads.

## If you later want real login + orders + database support

If you want this site to be fully dynamic with real data, the next architecture step would usually be something like:
- S3 for frontend hosting
- API Gateway + Lambda or EC2/ECS for backend logic
- Amazon RDS for users, products, carts, and orders

That would be a **different Terraform project design** than the static-only version here.

## Client-side routing note

If you later convert this site into a React, Vue, or Angular single-page app, set:

```hcl
error_document = "index.html"
```

That lets unknown routes fall back to the app entry point.
