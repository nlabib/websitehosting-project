# Custom Print Feature — Design Spec
**Date:** 2026-04-25

## Overview

Add a "Custom Print" tab to the CloudSev home page. Users can upload a design file, review it, and place a custom print order tied to their account.

---

## Architecture

### New AWS Resources
- **S3 bucket** `cloudsev-designs` — stores uploaded design files. Private, no public access. CORS rule allows PUT from any origin (required for presigned upload).
- **Lambda** `cloudsev-custom-print` — handles presigned URL generation and order creation.
- **API Gateway routes** — `POST /custom-print/upload-url` and `POST /custom-print/order`, wired to the new Lambda via the existing HTTP API.

### Changes to Existing Resources
- **`iam.tf`** — add `s3:PutObject` on `cloudsev-designs` to the existing `lambda_exec` role.
- **`api_gateway.tf`** — add two new routes/integrations; add `PUT` to CORS `allow_methods`.
- **`lambda.tf`** — new Lambda gets `DESIGNS_BUCKET` plus the shared `lambda_env` locals (JWT_SECRET, ORDERS_TABLE, etc.) merged together.

### Storage
No new DynamoDB table. Custom print orders are written to the existing `ORDERS_TABLE` with an extra `designKey` field. They appear in "Past Orders" automatically.

---

## Frontend — `CustomPrint.html`

Same navbar and design system as all other pages. Requires auth (`requireAuth()`).

**User flow:**
1. File picker (drag-and-drop or click). Accepts `image/*,.pdf`.
2. Preview: thumbnail for images, filename display for PDF.
3. Optional notes/instructions text field.
4. **"Upload & Review"** button — POSTs to `/custom-print/upload-url` to get a presigned URL, then PUTs the file directly to S3. Shows spinner during upload.
5. On success: confirmation panel shows filename, notes, and price ($25.00) with a **"Place Order"** button and a "Cancel" link.
6. **"Place Order"** — POSTs to `/custom-print/order` with `{ key, notes }`. On success: shows order ID confirmation.

**HomePage.html** — add a 5th nav card: icon 🎨, label "Custom Print", sub "Upload your design", href `CustomPrint.html`.

**`api.js`** — add two methods:
```js
getCustomPrintUploadUrl: (filename, contentType) =>
  apiCall("POST", "/custom-print/upload-url", { filename, contentType }),
placeCustomPrintOrder: (key, notes) =>
  apiCall("POST", "/custom-print/order", { key, notes }),
```

---

## Backend — Lambda `cloudsev-custom-print`

**Route: `POST /custom-print/upload-url`**
- Verifies JWT from `Authorization` header.
- Generates a presigned S3 `PUT` URL with 5-minute expiry.
- Key format: `uploads/{userId}/{uuid}.{ext}`
- Returns: `{ uploadUrl, key }`

**Route: `POST /custom-print/order`**
- Verifies JWT.
- Accepts `{ key, notes }`.
- Writes to `ORDERS_TABLE`:
  ```
  orderId    — uuid
  userId     — from JWT
  type       — "custom-print"
  designKey  — S3 key
  notes      — string (may be empty)
  total      — 25.00
  status     — "pending"
  createdAt  — ISO timestamp
  ```
- Returns: `{ orderId, total }`

---

## Terraform File Summary

| File | Change |
|------|--------|
| `s3.tf` | New file — S3 bucket with CORS |
| `lambda.tf` | New Lambda resource + zip; install deps null_resource |
| `iam.tf` | Add S3 PutObject permission to existing role |
| `api_gateway.tf` | 2 new routes, 1 new integration, 1 new permission; PUT in CORS |

---

## Price
Custom print orders are fixed at **$25.00**.

## Accepted File Types
`image/*` and `.pdf`
