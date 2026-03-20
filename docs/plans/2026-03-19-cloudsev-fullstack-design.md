# CloudSev Full-Stack Design — 2026-03-19

## Overview

Evolve CloudSev from a fully static S3 site into a functional serverless e-commerce storefront backed by DynamoDB, AWS Lambda, and API Gateway — all provisioned via Terraform and kept cheap enough to run on the AWS free tier.

---

## Architecture

```
Browser (S3 static site)
        │
        │  HTTPS fetch() calls
        ▼
  API Gateway (REST)
        │
        ▼
  Lambda functions (Python 3.12)
        │
        ▼
  DynamoDB (4 tables, on-demand billing)
```

All infrastructure is managed in Terraform alongside the existing S3 bucket setup.

**Cost profile:** near-zero at class-project traffic levels. DynamoDB on-demand, Lambda pay-per-invocation, and API Gateway pay-per-call all stay within the AWS free tier for low-volume use.

---

## DynamoDB Tables

| Table | Partition Key | Sort Key | Key Attributes |
|---|---|---|---|
| `cloudsev-users` | `userId` (S) | — | email, name, passwordHash |
| `cloudsev-products` | `productId` (S) | — | name, price, partNumber, imageUrl |
| `cloudsev-cart` | `userId` (S) | `productId` (S) | quantity |
| `cloudsev-orders` | `userId` (S) | `orderId` (S) | items, total, date, delivered |

All tables use `PAY_PER_REQUEST` billing. Products are seeded at deploy time via a Terraform `null_resource` that invokes a seeder Lambda.

---

## API Endpoints

| Method | Path | Auth? | Purpose |
|---|---|---|---|
| POST | `/auth/signup` | No | Create user, return JWT |
| POST | `/auth/login` | No | Verify password, return JWT |
| GET | `/products` | No | List all products |
| GET | `/cart` | Yes | Get logged-in user's cart |
| POST | `/cart` | Yes | Add/update item in cart |
| DELETE | `/cart/{productId}` | Yes | Remove item from cart |
| POST | `/orders` | Yes | Checkout — move cart to new order |
| GET | `/orders` | Yes | List user's past orders |

Authentication uses custom JWT (HS256). The JWT secret is stored as a Lambda environment variable. Authenticated routes validate the `Authorization: Bearer <token>` header inside each Lambda.

Lambda functions are written in Python 3.12 and packaged as zip archives uploaded via Terraform.

---

## Frontend Pages

All 5 pages are redesigned with modern custom CSS (replacing Bootstrap 2). Each page becomes dynamic using `fetch()`.

| Page | What changes |
|---|---|
| `Login.html` | Real login + signup forms calling `/auth/login` and `/auth/signup`; JWT stored in `localStorage` |
| `HomePage.html` | Displays user name decoded from JWT; navigation cards |
| `Products.html` | Fetches products from `/products`; "Add to Cart" calls `/cart`; shows cart item count badge |
| `AccountInfo.html` | Displays user info decoded from JWT |
| `UsersPastOrders.html` | Fetches real orders from `/orders` for the logged-in user |

All authenticated pages redirect to `Login.html` if no JWT is found in `localStorage`.

---

## Terraform Resources Added

- `aws_dynamodb_table` × 4
- `aws_iam_role` + `aws_iam_role_policy` for Lambda execution
- `aws_lambda_function` × 8 (one per route) or grouped
- `aws_lambda_function` × 1 (product seeder, invoked once)
- `aws_api_gateway_rest_api` with resources, methods, integrations, CORS
- `aws_api_gateway_deployment` + `aws_api_gateway_stage`
- `null_resource` to invoke seeder Lambda after deploy
- Updated `outputs.tf` to expose the API Gateway URL

---

## Security Notes

- Passwords stored as bcrypt hashes in DynamoDB
- JWT signed with HS256, 24-hour expiry
- API Gateway CORS configured to allow the S3 website origin
- No secrets committed to git; JWT secret passed via Terraform variable
