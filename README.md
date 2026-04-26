# CloudSev — Serverless E-Commerce on AWS

CloudSev is a fully serverless e-commerce platform with a static frontend, REST API, and custom-print upload feature. All infrastructure is managed by Terraform.

**Live URLs**
- Frontend: `http://phase2-website.s3-website-us-east-1.amazonaws.com`
- API base: `https://tvclw1m9p7.execute-api.us-east-1.amazonaws.com`

---

## Architecture

```
Browser
  │
  │  Static assets (HTML/CSS/JS)
  ▼
┌─────────────────────────────┐
│  S3 Static Website Hosting  │  bucket: phase2-website
│  (index.html, Login.html,   │
│   HomePage.html, ...)       │
└─────────────────────────────┘
  │
  │  REST API calls (fetch)
  ▼
┌──────────────────────────────────────────────┐
│       API Gateway v2 (HTTP API)              │
│       tvclw1m9p7.execute-api.us-east-1...    │
│                                              │
│  POST /auth/signup          ──►  cloudsev-auth          │
│  POST /auth/login           ──►  cloudsev-auth          │
│  GET  /products             ──►  cloudsev-products      │
│  GET  /cart                 ──►  cloudsev-cart          │
│  POST /cart                 ──►  cloudsev-cart          │
│  DELETE /cart/{productId}   ──►  cloudsev-cart          │
│  POST /orders               ──►  cloudsev-orders        │
│  GET  /orders               ──►  cloudsev-orders        │
│  POST /custom-print/upload-url ─► cloudsev-custom-print │
│  POST /custom-print/order   ──►  cloudsev-custom-print  │
└──────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────┐
│                  AWS Lambda (Python 3.12)            │
│                                                     │
│  cloudsev-auth          signup / login, JWT issue   │
│  cloudsev-products      product catalogue (read)    │
│  cloudsev-cart          cart CRUD per user          │
│  cloudsev-orders        checkout + order history    │
│  cloudsev-custom-print  presigned URL + order write │
│  cloudsev-seeder        (admin) seed product data   │
└──────────┬──────────────────────────┬───────────────┘
           │ reads/writes             │ presigned PUT URL
           ▼                          ▼
┌──────────────────────┐    ┌──────────────────────┐
│     DynamoDB         │    │  S3 bucket           │
│                      │    │  cloudsev-designs    │
│  cloudsev-users      │    │  (private; design    │
│  cloudsev-products   │    │   files uploaded     │
│  cloudsev-cart       │    │   directly from      │
│  cloudsev-orders     │    │   the browser via    │
└──────────────────────┘    │   presigned URL)     │
                            └──────────────────────┘
```

### Request flow: Custom Print upload

```
1. Browser  ──POST /custom-print/upload-url──►  cloudsev-custom-print Lambda
               { filename, contentType }
               ◄── { uploadUrl (presigned PUT), key }

2. Browser  ──PUT <uploadUrl>──►  S3 cloudsev-designs  (direct, bypasses API GW)
               raw file bytes

3. Browser  ──POST /custom-print/order──►  cloudsev-custom-print Lambda
               { key, notes }
               ◄── { orderId, total: "25.00" }
               (order written to cloudsev-orders DynamoDB table)
```

### Auth flow

```
1. POST /auth/signup or /auth/login  →  cloudsev-auth Lambda
2. Lambda returns a signed JWT (HS256, secret in Lambda env)
3. Browser stores JWT in localStorage
4. Every subsequent API call includes:   Authorization: Bearer <jwt>
5. Each Lambda verifies the JWT before processing the request
```

---

## AWS Resources

### Compute

| Resource | Name | Purpose |
|----------|------|---------|
| Lambda | `cloudsev-auth` | User registration and login; issues JWTs |
| Lambda | `cloudsev-products` | Returns product catalogue |
| Lambda | `cloudsev-cart` | Per-user cart (add, remove, view) |
| Lambda | `cloudsev-orders` | Checkout (cart → order) and order history |
| Lambda | `cloudsev-custom-print` | Presigned S3 URL generation + custom-print orders |
| Lambda | `cloudsev-seeder` | One-time admin utility to seed product data |

### API

| Resource | ID | Details |
|----------|----|---------|
| API Gateway v2 (HTTP) | `tvclw1m9p7` | Single HTTP API; CORS enabled for all origins |

### Storage

| Resource | Name | Purpose |
|----------|------|---------|
| S3 bucket | `phase2-website` | Static website hosting (public-read) |
| S3 bucket | `cloudsev-designs` | Design file uploads (private; presigned PUT only) |
| DynamoDB table | `cloudsev-users` | User accounts (PK: `userId`) |
| DynamoDB table | `cloudsev-products` | Product catalogue (PK: `productId`) |
| DynamoDB table | `cloudsev-cart` | Cart items (PK: `userId`, SK: `productId`) |
| DynamoDB table | `cloudsev-orders` | All orders incl. custom-print (PK: `userId`, SK: `orderId`) |

### IAM

| Resource | Purpose |
|----------|---------|
| Role `cloudsev-lambda-exec` | Execution role shared by all Lambdas |
| Policy (inline) | DynamoDB full access on all cloudsev tables |
| Policy (inline) | S3 `PutObject` on `cloudsev-designs/*` |

---

## Project Structure

```
.
├── main.tf               # Provider + S3 static site bucket
├── variables.tf
├── outputs.tf            # website_url, api_url
├── providers.tf
├── terraform.tfvars      # Your bucket name + region (git-ignored)
├── terraform.tfvars.example
│
├── dynamodb.tf           # 4 DynamoDB tables
├── iam.tf                # Lambda execution role + policies
├── lambda.tf             # All 6 Lambda functions
├── api_gateway.tf        # HTTP API + all routes + CORS
├── s3.tf                 # cloudsev-designs bucket + CORS
│
├── lambda/
│   ├── auth/             # handler.py + requirements.txt
│   ├── cart/
│   ├── custom-print/
│   ├── orders/
│   ├── products/
│   └── seeder/
│
├── website/
│   ├── index.html        # Redirects to Login.html
│   ├── Login.html
│   ├── HomePage.html     # Nav cards to all features
│   ├── Products.html
│   ├── AccountInfo.html
│   ├── UsersPastOrders.html
│   ├── CustomPrint.html  # File upload + order placement
│   ├── css/
│   └── js/
│       └── api.js        # Shared fetch helper + auth utils
│
└── tests/
    ├── conftest.py       # moto-based DynamoDB + S3 fixtures
    ├── test_auth.py
    ├── test_cart.py
    ├── test_orders.py
    ├── test_products.py
    └── test_custom_print.py
```

---

## Deploy

### Prerequisites

- AWS CLI configured (`aws configure`)
- Terraform >= 1.3
- Python 3.12 (for Lambda packaging)

### First deploy

```bash
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars — set bucket_name to a globally unique name

terraform init
terraform plan
terraform apply
```

After apply:

```bash
terraform output website_url   # open this in your browser
terraform output api_url       # used by api.js
```

### Re-deploy after code changes

```bash
terraform apply   # re-zips and re-uploads changed Lambdas + website files
```

### Tear down

```bash
terraform destroy
```

---

## Run Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Tests use [moto](https://github.com/getmoto/moto) to mock DynamoDB and S3 — no real AWS calls.

---

## Pages

| Page | Auth required | Description |
|------|--------------|-------------|
| `Login.html` | No | Sign up or log in |
| `HomePage.html` | Yes | Navigation hub |
| `Products.html` | Yes | Browse and add items to cart |
| `AccountInfo.html` | Yes | View account details |
| `UsersPastOrders.html` | Yes | Order history (regular + custom-print) |
| `CustomPrint.html` | Yes | Upload a design file, place custom-print order ($25) |
