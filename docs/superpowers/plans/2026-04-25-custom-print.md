# Custom Print Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Custom Print" tab to CloudSev where logged-in users can upload a design file to S3 and place a $25 custom print order tied to their account.

**Architecture:** A new `cloudsev-custom-print` Lambda handles two routes — `POST /custom-print/upload-url` returns a presigned S3 PUT URL, and `POST /custom-print/order` records the order in the existing `ORDERS_TABLE` DynamoDB table. The frontend uploads the file directly to S3 using the presigned URL, then separately places the order only if the user confirms.

**Tech Stack:** Python 3.12 (Lambda), PyJWT, boto3, moto (tests), Terraform (AWS infra), vanilla HTML/CSS/JS (frontend).

---

## Task 1: Update conftest + write failing custom-print Lambda tests

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/test_custom_print.py`

- [ ] **Step 1: Add DESIGNS_BUCKET env var and S3 bucket to conftest**

In `tests/conftest.py`, add `os.environ["DESIGNS_BUCKET"] = "cloudsev-designs"` after the existing env var block, and create the S3 bucket inside `aws_tables` fixture:

```python
import os
import pytest
import boto3
from moto import mock_aws

os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["USERS_TABLE"] = "cloudsev-users"
os.environ["PRODUCTS_TABLE"] = "cloudsev-products"
os.environ["CART_TABLE"] = "cloudsev-cart"
os.environ["ORDERS_TABLE"] = "cloudsev-orders"
os.environ["DESIGNS_BUCKET"] = "cloudsev-designs"


@pytest.fixture
def aws_tables():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        # users
        client.create_table(
            TableName="cloudsev-users",
            KeySchema=[{"AttributeName": "userId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "userId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        # products
        client.create_table(
            TableName="cloudsev-products",
            KeySchema=[{"AttributeName": "productId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "productId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        # cart
        client.create_table(
            TableName="cloudsev-cart",
            KeySchema=[
                {"AttributeName": "userId", "KeyType": "HASH"},
                {"AttributeName": "productId", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "userId", "AttributeType": "S"},
                {"AttributeName": "productId", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        # orders
        client.create_table(
            TableName="cloudsev-orders",
            KeySchema=[
                {"AttributeName": "userId", "KeyType": "HASH"},
                {"AttributeName": "orderId", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "userId", "AttributeType": "S"},
                {"AttributeName": "orderId", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        # designs bucket
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="cloudsev-designs")
        yield
```

- [ ] **Step 2: Write failing tests for custom-print Lambda**

Create `tests/test_custom_print.py`:

```python
import json
import importlib.util
import os
import boto3

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(rel_path, mod_name):
    path = os.path.join(PROJECT_ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _signup_token(auth, email="cp@test.com"):
    resp = auth.lambda_handler(
        {
            "routeKey": "POST /auth/signup",
            "body": json.dumps({"name": "CP User", "email": email, "password": "pw"}),
            "headers": {},
        },
        None,
    )
    return json.loads(resp["body"])["token"]


def _event(route, token, body=None):
    return {
        "routeKey": route,
        "headers": {"authorization": f"Bearer {token}"},
        "body": json.dumps(body) if body else None,
        "pathParameters": {},
    }


def test_upload_url_returns_url_and_key(aws_tables):
    auth = _load("lambda/auth/handler.py", "_auth_cp1")
    cp = _load("lambda/custom-print/handler.py", "_cp_h1")
    token = _signup_token(auth)
    resp = cp.lambda_handler(
        _event(
            "POST /custom-print/upload-url",
            token,
            {"filename": "design.png", "contentType": "image/png"},
        ),
        None,
    )
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "uploadUrl" in body
    assert "key" in body
    assert body["key"].startswith("uploads/")
    assert body["key"].endswith(".png")


def test_upload_url_unauthenticated_returns_401(aws_tables):
    cp = _load("lambda/custom-print/handler.py", "_cp_h2")
    resp = cp.lambda_handler(
        {
            "routeKey": "POST /custom-print/upload-url",
            "headers": {},
            "body": None,
            "pathParameters": {},
        },
        None,
    )
    assert resp["statusCode"] == 401


def test_place_order_creates_dynamo_record(aws_tables):
    auth = _load("lambda/auth/handler.py", "_auth_cp3")
    cp = _load("lambda/custom-print/handler.py", "_cp_h3")
    token = _signup_token(auth, "cp2@test.com")
    resp = cp.lambda_handler(
        _event(
            "POST /custom-print/order",
            token,
            {"key": "uploads/abc/xyz.png", "notes": "blue ink on front"},
        ),
        None,
    )
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "orderId" in body
    assert body["total"] == "25.00"


def test_place_order_without_notes(aws_tables):
    auth = _load("lambda/auth/handler.py", "_auth_cp4")
    cp = _load("lambda/custom-print/handler.py", "_cp_h4")
    token = _signup_token(auth, "cp3@test.com")
    resp = cp.lambda_handler(
        _event(
            "POST /custom-print/order",
            token,
            {"key": "uploads/abc/xyz.pdf"},
        ),
        None,
    )
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["total"] == "25.00"


def test_place_order_missing_key_returns_400(aws_tables):
    auth = _load("lambda/auth/handler.py", "_auth_cp5")
    cp = _load("lambda/custom-print/handler.py", "_cp_h5")
    token = _signup_token(auth, "cp4@test.com")
    resp = cp.lambda_handler(
        _event("POST /custom-print/order", token, {"notes": "no key here"}),
        None,
    )
    assert resp["statusCode"] == 400


def test_place_order_unauthenticated_returns_401(aws_tables):
    cp = _load("lambda/custom-print/handler.py", "_cp_h6")
    resp = cp.lambda_handler(
        {
            "routeKey": "POST /custom-print/order",
            "headers": {},
            "body": json.dumps({"key": "uploads/abc/xyz.png"}),
            "pathParameters": {},
        },
        None,
    )
    assert resp["statusCode"] == 401
```

- [ ] **Step 3: Run tests to verify they all fail with "No such file or directory"**

```bash
cd "/Users/nasimullabib/Library/CloudStorage/OneDrive-KennesawStateUniversity/School/Kennesaw State/Years/4th year/Spring/Cloud Software Development/2nd-Group-Project"
pytest tests/test_custom_print.py -v
```

Expected: all 6 tests FAIL — `No such file or directory: '.../lambda/custom-print/handler.py'`

---

## Task 2: Implement the custom-print Lambda

**Files:**
- Create: `lambda/custom-print/requirements.txt`
- Create: `lambda/custom-print/handler.py`

- [ ] **Step 1: Create requirements.txt**

Create `lambda/custom-print/requirements.txt`:

```
PyJWT>=2.8.0
```

- [ ] **Step 2: Create the Lambda handler**

Create `lambda/custom-print/handler.py`:

```python
import json
import os
import uuid
import boto3
import jwt
from datetime import datetime, timezone

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")


def _ok(body):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _err(status, msg):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": msg}),
    }


def _get_user_id(event):
    auth = (event.get("headers") or {}).get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(auth[7:], os.environ["JWT_SECRET"], algorithms=["HS256"])
        return payload["sub"]
    except Exception:
        return None


def _generate_upload_url(user_id, body):
    filename = body.get("filename", "design")
    content_type = body.get("contentType", "application/octet-stream")
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    key = f"uploads/{user_id}/{uuid.uuid4().hex}.{ext}"
    bucket = os.environ["DESIGNS_BUCKET"]
    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=300,
    )
    return _ok({"uploadUrl": url, "key": key})


def _place_order(user_id, body):
    key = body.get("key")
    if not key:
        return _err(400, "key required")
    notes = body.get("notes", "")
    orders_table = dynamodb.Table(os.environ["ORDERS_TABLE"])
    order_id = uuid.uuid4().hex
    date_str = datetime.now(timezone.utc).strftime("%B %-d, %Y")
    orders_table.put_item(Item={
        "userId": user_id,
        "orderId": order_id,
        "type": "custom-print",
        "designKey": key,
        "notes": notes,
        "total": "25.00",
        "date": date_str,
        "delivered": False,
    })
    return _ok({"orderId": order_id, "total": "25.00"})


def lambda_handler(event, context):
    user_id = _get_user_id(event)
    if not user_id:
        return _err(401, "unauthorized")
    route = event.get("routeKey", "")
    if route == "POST /custom-print/upload-url":
        return _generate_upload_url(user_id, json.loads(event.get("body") or "{}"))
    if route == "POST /custom-print/order":
        return _place_order(user_id, json.loads(event.get("body") or "{}"))
    return _err(404, "not found")
```

- [ ] **Step 3: Run tests to verify they all pass**

```bash
pytest tests/test_custom_print.py -v
```

Expected output:
```
test_custom_print.py::test_upload_url_returns_url_and_key PASSED
test_custom_print.py::test_upload_url_unauthenticated_returns_401 PASSED
test_custom_print.py::test_place_order_creates_dynamo_record PASSED
test_custom_print.py::test_place_order_without_notes PASSED
test_custom_print.py::test_place_order_missing_key_returns_400 PASSED
test_custom_print.py::test_place_order_unauthenticated_returns_401 PASSED
6 passed
```

- [ ] **Step 4: Run the full test suite to confirm no regressions**

```bash
pytest -v
```

Expected: all existing tests still pass.

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/test_custom_print.py lambda/custom-print/handler.py lambda/custom-print/requirements.txt
git commit -m "feat: add custom-print Lambda with presigned URL and order creation"
```

---

## Task 3: Update orders Lambda to expose custom-print fields in list

The `_list_orders` function in `lambda/orders/handler.py` doesn't return `type`, `designKey`, or `notes`. Custom-print orders will appear in Past Orders as empty-item orders unless we pass those fields through.

**Files:**
- Modify: `lambda/orders/handler.py:86-110`
- Modify: `tests/test_orders.py`

- [ ] **Step 1: Write a failing test for custom-print order fields in order list**

Add this test to `tests/test_orders.py`:

```python
def test_list_orders_includes_custom_print_fields(aws_tables):
    auth = _load("lambda/auth/handler.py", "_auth_ord4")
    orders = _load("lambda/orders/handler.py", "_orders_h4")
    token = _signup_token(auth, "cp@orders.com")
    # Directly write a custom-print order to DynamoDB
    table = boto3.resource("dynamodb", region_name="us-east-1").Table("cloudsev-orders")
    import jwt as _jwt
    user_id = _jwt.decode(token, "test-secret-key", algorithms=["HS256"])["sub"]
    table.put_item(Item={
        "userId": user_id,
        "orderId": "test-order-001",
        "type": "custom-print",
        "designKey": "uploads/abc/logo.png",
        "notes": "red ink",
        "total": "25.00",
        "date": "April 25, 2026",
        "delivered": False,
    })
    resp = orders.lambda_handler(_event("GET /orders", token), None)
    assert resp["statusCode"] == 200
    order_list = json.loads(resp["body"])
    assert len(order_list) == 1
    o = order_list[0]
    assert o["type"] == "custom-print"
    assert o["designKey"] == "uploads/abc/logo.png"
    assert o["notes"] == "red ink"
```

- [ ] **Step 2: Run the new test to confirm it fails**

```bash
pytest tests/test_orders.py::test_list_orders_includes_custom_print_fields -v
```

Expected: FAIL — `KeyError: 'type'` or assertion error.

- [ ] **Step 3: Update `_list_orders` in `lambda/orders/handler.py`**

Replace the `_list_orders` function (lines 86–110):

```python
def _list_orders(user_id):
    orders_table = dynamodb.Table(os.environ["ORDERS_TABLE"])
    resp = orders_table.query(
        KeyConditionExpression=Key("userId").eq(user_id),
        ScanIndexForward=False,
    )
    orders = []
    for o in resp.get("Items", []):
        items = []
        for item in o.get("items", []):
            items.append({
                "productId": item.get("productId", ""),
                "name": item.get("name", ""),
                "partNumber": item.get("partNumber", ""),
                "price": str(item.get("price", "0")),
                "quantity": int(item.get("quantity", 1)),
            })
        order_data = {
            "orderId": o["orderId"],
            "total": str(o.get("total", "0")),
            "date": o.get("date", ""),
            "delivered": bool(o.get("delivered", False)),
            "items": items,
        }
        if o.get("type") == "custom-print":
            order_data["type"] = "custom-print"
            order_data["designKey"] = o.get("designKey", "")
            order_data["notes"] = o.get("notes", "")
        orders.append(order_data)
    return _ok(orders)
```

- [ ] **Step 4: Run all orders tests to verify they pass**

```bash
pytest tests/test_orders.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add lambda/orders/handler.py tests/test_orders.py
git commit -m "feat: expose type/designKey/notes for custom-print orders in list endpoint"
```

---

## Task 4: Terraform — S3 bucket

**Files:**
- Create: `s3.tf`

- [ ] **Step 1: Create `s3.tf`**

```hcl
resource "aws_s3_bucket" "designs" {
  bucket = "cloudsev-designs"
  tags   = { Project = "cloudsev", ManagedBy = "Terraform" }
}

resource "aws_s3_bucket_public_access_block" "designs" {
  bucket                  = aws_s3_bucket.designs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_cors_configuration" "designs" {
  bucket = aws_s3_bucket.designs.id

  cors_rule {
    allowed_methods = ["PUT"]
    allowed_origins = ["*"]
    allowed_headers = ["*"]
    max_age_seconds = 3000
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add s3.tf
git commit -m "feat: add S3 designs bucket with CORS for presigned uploads"
```

---

## Task 5: Terraform — IAM S3 policy

**Files:**
- Modify: `iam.tf`

- [ ] **Step 1: Append S3 PutObject policy to `iam.tf`**

Add at the end of `iam.tf`:

```hcl
data "aws_iam_policy_document" "s3_designs_access" {
  statement {
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.designs.arn}/*"]
  }
}

resource "aws_iam_role_policy" "s3_designs_access" {
  name   = "cloudsev-s3-designs-access"
  role   = aws_iam_role.lambda_exec.id
  policy = data.aws_iam_policy_document.s3_designs_access.json
}
```

- [ ] **Step 2: Commit**

```bash
git add iam.tf
git commit -m "feat: grant lambda_exec role s3:PutObject on designs bucket"
```

---

## Task 6: Terraform — custom-print Lambda

**Files:**
- Modify: `lambda.tf`

- [ ] **Step 1: Append custom-print Lambda resources to `lambda.tf`**

Add at the end of `lambda.tf` (after the seeder block):

```hcl
resource "null_resource" "install_custom_print_deps" {
  triggers = {
    req_hash = filemd5("${path.module}/lambda/custom-print/requirements.txt")
  }
  provisioner "local-exec" {
    command = "pip3 install -r ${path.module}/lambda/custom-print/requirements.txt -t ${path.module}/lambda/custom-print/ --quiet --upgrade"
  }
}

data "archive_file" "custom_print_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/custom-print"
  output_path = "${path.module}/lambda/custom-print.zip"
  excludes    = ["requirements.txt", "__pycache__"]
  depends_on  = [null_resource.install_custom_print_deps]
}

resource "aws_lambda_function" "custom_print" {
  filename         = data.archive_file.custom_print_zip.output_path
  function_name    = "cloudsev-custom-print"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.custom_print_zip.output_base64sha256
  timeout          = 15
  environment {
    variables = merge(local.lambda_env, {
      DESIGNS_BUCKET = aws_s3_bucket.designs.bucket
    })
  }
  tags = { Project = "cloudsev", ManagedBy = "Terraform" }
}
```

- [ ] **Step 2: Commit**

```bash
git add lambda.tf
git commit -m "feat: add cloudsev-custom-print Lambda terraform resource"
```

---

## Task 7: Terraform — API Gateway routes

**Files:**
- Modify: `api_gateway.tf`

- [ ] **Step 1: Add `PUT` to CORS allow_methods**

In `api_gateway.tf`, change the `cors_configuration` block inside `aws_apigatewayv2_api.cloudsev`:

Old:
```hcl
    allow_methods = ["GET", "POST", "DELETE", "OPTIONS"]
```

New:
```hcl
    allow_methods = ["GET", "POST", "DELETE", "OPTIONS", "PUT"]
```

- [ ] **Step 2: Append integration, routes, and permission**

Add at the end of `api_gateway.tf` (after the seeder block):

```hcl
resource "aws_apigatewayv2_integration" "custom_print" {
  api_id                 = aws_apigatewayv2_api.cloudsev.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.custom_print.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "custom_print_upload_url" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "POST /custom-print/upload-url"
  target    = "integrations/${aws_apigatewayv2_integration.custom_print.id}"
}

resource "aws_apigatewayv2_route" "custom_print_order" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "POST /custom-print/order"
  target    = "integrations/${aws_apigatewayv2_integration.custom_print.id}"
}

resource "aws_lambda_permission" "custom_print_apigw" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.custom_print.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.cloudsev.execution_arn}/*/*"
}
```

- [ ] **Step 3: Commit**

```bash
git add api_gateway.tf
git commit -m "feat: add API Gateway routes for custom-print Lambda"
```

---

## Task 8: Frontend — api.js methods

**Files:**
- Modify: `website/js/api.js`

- [ ] **Step 1: Add two methods to the `api` object**

In `website/js/api.js`, add two entries inside the `api` object after `getOrders`:

Old:
```js
  getOrders: () => apiCall("GET", "/orders"),
};
```

New:
```js
  getOrders: () => apiCall("GET", "/orders"),
  getCustomPrintUploadUrl: (filename, contentType) =>
    apiCall("POST", "/custom-print/upload-url", { filename, contentType }),
  placeCustomPrintOrder: (key, notes) =>
    apiCall("POST", "/custom-print/order", { key, notes }),
};
```

- [ ] **Step 2: Commit**

```bash
git add website/js/api.js
git commit -m "feat: add getCustomPrintUploadUrl and placeCustomPrintOrder to api.js"
```

---

## Task 9: Frontend — CustomPrint.html

**Files:**
- Create: `website/CustomPrint.html`

- [ ] **Step 1: Create `website/CustomPrint.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>CloudSev | Custom Print</title>
  <link rel="stylesheet" href="css/app.css" />
</head>
<body>
<nav class="navbar">
  <a class="navbar-brand" href="HomePage.html"><span>Cloud</span>Sev</a>
  <div class="navbar-links">
    <a href="Products.html">Products</a>
    <a href="UsersPastOrders.html">Orders</a>
    <a href="AccountInfo.html">Account</a>
    <button onclick="logout()">Logout</button>
  </div>
</nav>

<div class="container" style="padding-top:2rem; padding-bottom:3rem;">
  <div class="page-header">
    <h1>Custom Print</h1>
    <a href="HomePage.html" class="btn btn-secondary btn-sm">← Home</a>
  </div>

  <div id="alert" class="alert alert-error" style="display:none"></div>
  <div id="alert-success" class="alert alert-success" style="display:none"></div>

  <div id="upload-section" class="card card-wide" style="max-width:100%;">
    <h2 style="font-size:1.1rem; margin-bottom:1.25rem;">Upload Your Design</h2>

    <div class="form-group">
      <label>Design File</label>
      <div id="drop-zone"
        style="border:2px dashed var(--border); border-radius:var(--radius); padding:2.5rem; text-align:center; cursor:pointer; transition:border-color var(--transition);"
        onclick="document.getElementById('file-input').click()">
        <div style="font-size:2.5rem; margin-bottom:0.5rem;">🎨</div>
        <p style="color:var(--text-muted); margin-bottom:0.5rem;">Drag &amp; drop or click to browse</p>
        <p style="font-size:0.8rem; color:var(--text-muted);">Accepted: images (PNG, JPG, GIF, etc.) and PDF</p>
      </div>
      <input type="file" id="file-input" accept="image/*,.pdf" style="display:none" />
    </div>

    <div id="preview-section" style="display:none; margin-bottom:1.25rem;">
      <label>Selected File</label>
      <div style="display:flex; align-items:center; gap:1rem; background:var(--surface-2); border:1px solid var(--border); border-radius:var(--radius-sm); padding:0.75rem 1rem;">
        <img id="preview-img" src="" alt="preview" style="width:60px; height:60px; object-fit:cover; border-radius:4px; display:none;" />
        <div id="preview-icon" style="font-size:2rem; display:none;">📄</div>
        <div>
          <div id="preview-name" style="font-weight:600;"></div>
          <div id="preview-size" style="font-size:0.8rem; color:var(--text-muted);"></div>
        </div>
        <button class="btn btn-danger" style="margin-left:auto;" onclick="clearFile()">✕</button>
      </div>
    </div>

    <div class="form-group">
      <label>Notes (optional)</label>
      <input type="text" id="notes" placeholder="e.g. print on front, size L, blue ink…" />
    </div>

    <button class="btn btn-primary" id="upload-btn" onclick="uploadAndReview()" disabled>Upload &amp; Review</button>
  </div>

  <div id="confirm-section" class="card card-wide" style="display:none; max-width:100%; margin-top:1.5rem;">
    <h2 style="font-size:1.1rem; margin-bottom:1.25rem;">Review Your Order</h2>
    <ul class="info-list">
      <li><strong>File</strong> <span id="confirm-file"></span></li>
      <li><strong>Notes</strong> <span id="confirm-notes"></span></li>
      <li><strong>Price</strong> <span style="color:var(--gold); font-weight:700;">$25.00</span></li>
    </ul>
    <div style="display:flex; gap:0.75rem; margin-top:1.25rem; flex-wrap:wrap;">
      <button class="btn btn-primary" style="width:auto;" id="order-btn" onclick="placeOrder()">Place Order</button>
      <button class="btn btn-secondary btn-sm" onclick="cancelOrder()">Cancel</button>
    </div>
  </div>
</div>

<script src="js/api.js"></script>
<script>
  if (!requireAuth()) throw new Error("redirecting");

  let uploadedKey = null;
  let selectedFile = null;

  const fileInput = document.getElementById("file-input");
  const dropZone = document.getElementById("drop-zone");

  fileInput.addEventListener("change", () => {
    if (fileInput.files[0]) setFile(fileInput.files[0]);
  });

  dropZone.addEventListener("dragover", e => {
    e.preventDefault();
    dropZone.style.borderColor = "var(--gold)";
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.style.borderColor = "var(--border)";
  });

  dropZone.addEventListener("drop", e => {
    e.preventDefault();
    dropZone.style.borderColor = "var(--border)";
    if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
  });

  function setFile(file) {
    selectedFile = file;
    document.getElementById("preview-name").textContent = file.name;
    document.getElementById("preview-size").textContent = (file.size / 1024).toFixed(1) + " KB";
    document.getElementById("preview-section").style.display = "";
    document.getElementById("upload-btn").disabled = false;
    const img = document.getElementById("preview-img");
    const icon = document.getElementById("preview-icon");
    if (file.type.startsWith("image/")) {
      img.src = URL.createObjectURL(file);
      img.style.display = "";
      icon.style.display = "none";
    } else {
      img.style.display = "none";
      icon.style.display = "";
    }
  }

  function clearFile() {
    selectedFile = null;
    fileInput.value = "";
    document.getElementById("preview-section").style.display = "none";
    document.getElementById("upload-btn").disabled = true;
  }

  async function uploadAndReview() {
    const btn = document.getElementById("upload-btn");
    btn.disabled = true;
    btn.textContent = "Uploading…";
    document.getElementById("alert").style.display = "none";
    try {
      const { uploadUrl, key } = await api.getCustomPrintUploadUrl(
        selectedFile.name,
        selectedFile.type || "application/octet-stream"
      );
      await fetch(uploadUrl, {
        method: "PUT",
        body: selectedFile,
        headers: { "Content-Type": selectedFile.type || "application/octet-stream" },
      });
      uploadedKey = key;
      document.getElementById("confirm-file").textContent = selectedFile.name;
      document.getElementById("confirm-notes").textContent =
        document.getElementById("notes").value || "—";
      document.getElementById("upload-section").style.display = "none";
      document.getElementById("confirm-section").style.display = "";
    } catch (err) {
      const alertEl = document.getElementById("alert");
      alertEl.textContent = err.message;
      alertEl.style.display = "";
      btn.disabled = false;
      btn.textContent = "Upload & Review";
    }
  }

  async function placeOrder() {
    const btn = document.getElementById("order-btn");
    btn.disabled = true;
    btn.textContent = "Placing…";
    document.getElementById("alert").style.display = "none";
    try {
      const notes = document.getElementById("notes").value;
      const { orderId } = await api.placeCustomPrintOrder(uploadedKey, notes);
      document.getElementById("confirm-section").style.display = "none";
      const success = document.getElementById("alert-success");
      success.textContent = `Order placed! Order ID: ${orderId.slice(0, 8).toUpperCase()}`;
      success.style.display = "";
    } catch (err) {
      const alertEl = document.getElementById("alert");
      alertEl.textContent = err.message;
      alertEl.style.display = "";
      btn.disabled = false;
      btn.textContent = "Place Order";
    }
  }

  function cancelOrder() {
    uploadedKey = null;
    document.getElementById("confirm-section").style.display = "none";
    document.getElementById("upload-section").style.display = "";
    document.getElementById("upload-btn").disabled = !selectedFile;
    document.getElementById("upload-btn").textContent = "Upload & Review";
  }
</script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add website/CustomPrint.html
git commit -m "feat: add CustomPrint.html with file upload and order confirmation flow"
```

---

## Task 10: Frontend — HomePage nav card + UsersPastOrders custom-print display

**Files:**
- Modify: `website/HomePage.html`
- Modify: `website/UsersPastOrders.html`

- [ ] **Step 1: Add Custom Print nav card to `website/HomePage.html`**

After the Account nav card, add:

Old:
```html
    <a class="nav-card" href="AccountInfo.html">
      <div class="nav-card-icon">👤</div>
      <div class="nav-card-label">Account</div>
      <div class="nav-card-sub">Your profile</div>
    </a>
  </div>
```

New:
```html
    <a class="nav-card" href="AccountInfo.html">
      <div class="nav-card-icon">👤</div>
      <div class="nav-card-label">Account</div>
      <div class="nav-card-sub">Your profile</div>
    </a>
    <a class="nav-card" href="CustomPrint.html">
      <div class="nav-card-icon">🎨</div>
      <div class="nav-card-label">Custom Print</div>
      <div class="nav-card-sub">Upload your design</div>
    </a>
  </div>
```

- [ ] **Step 2: Update `website/UsersPastOrders.html` to render custom-print orders**

In `UsersPastOrders.html`, replace the `renderOrders` function's order card innerHTML to handle custom-print orders. Replace:

Old:
```js
    container.innerHTML = orders.map(order => `
      <div class="card card-wide" style="max-width:100%; margin-bottom:1.5rem;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem; flex-wrap:wrap; gap:0.5rem;">
          <div>
            <div style="font-weight:700;">Order #${order.orderId.slice(0,8).toUpperCase()}</div>
            <div style="font-size:0.85rem; color:var(--text-muted);">${order.date}</div>
          </div>
          <div style="display:flex; align-items:center; gap:1rem;">
            <span style="font-size:1.2rem; font-weight:700; color:var(--gold);">$${parseFloat(order.total).toFixed(2)}</span>
            <span class="badge ${order.delivered ? 'badge-success' : 'badge-pending'}">${order.delivered ? 'Delivered' : 'Pending'}</span>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Item</th>
                <th>Part #</th>
                <th>Price</th>
                <th>Qty</th>
              </tr>
            </thead>
            <tbody>
              ${(order.items || []).map(item => `
                <tr>
                  <td>${item.name}</td>
                  <td style="color:var(--text-muted);">${item.partNumber}</td>
                  <td>$${parseFloat(item.price).toFixed(2)}</td>
                  <td>${item.quantity}</td>
                </tr>`).join("")}
            </tbody>
          </table>
        </div>
      </div>`).join("");
```

New:
```js
    container.innerHTML = orders.map(order => `
      <div class="card card-wide" style="max-width:100%; margin-bottom:1.5rem;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem; flex-wrap:wrap; gap:0.5rem;">
          <div>
            <div style="font-weight:700;">Order #${order.orderId.slice(0,8).toUpperCase()}${order.type === 'custom-print' ? ' <span style="font-size:0.75rem; color:var(--gold); font-weight:400;">Custom Print</span>' : ''}</div>
            <div style="font-size:0.85rem; color:var(--text-muted);">${order.date}</div>
          </div>
          <div style="display:flex; align-items:center; gap:1rem;">
            <span style="font-size:1.2rem; font-weight:700; color:var(--gold);">$${parseFloat(order.total).toFixed(2)}</span>
            <span class="badge ${order.delivered ? 'badge-success' : 'badge-pending'}">${order.delivered ? 'Delivered' : 'Pending'}</span>
          </div>
        </div>
        ${order.type === 'custom-print'
          ? `<ul class="info-list">
               <li><strong>Design</strong> <span>${order.designKey ? order.designKey.split('/').pop() : '—'}</span></li>
               <li><strong>Notes</strong> <span>${order.notes || '—'}</span></li>
             </ul>`
          : `<div class="table-wrap">
               <table>
                 <thead>
                   <tr><th>Item</th><th>Part #</th><th>Price</th><th>Qty</th></tr>
                 </thead>
                 <tbody>
                   ${(order.items || []).map(item => `
                     <tr>
                       <td>${item.name}</td>
                       <td style="color:var(--text-muted);">${item.partNumber}</td>
                       <td>$${parseFloat(item.price).toFixed(2)}</td>
                       <td>${item.quantity}</td>
                     </tr>`).join("")}
                 </tbody>
               </table>
             </div>`}
      </div>`).join("");
```

- [ ] **Step 3: Run the full test suite one final time**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 4: Final commit**

```bash
git add website/HomePage.html website/UsersPastOrders.html
git commit -m "feat: add Custom Print nav card and handle custom-print display in Past Orders"
```

---

## Deploy

After all tasks are complete, deploy with Terraform:

```bash
terraform init   # if first time or new providers
terraform plan
terraform apply
```

Verify:
1. `terraform apply` completes with no errors
2. S3 bucket `cloudsev-designs` exists in AWS console
3. Lambda `cloudsev-custom-print` is deployed
4. API Gateway has routes `POST /custom-print/upload-url` and `POST /custom-print/order`
5. Open the site → Home → Custom Print card appears → upload a file → confirm → place order → check Past Orders shows the custom print order
