# CloudSev Full-Stack Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform CloudSev from a static S3 site into a working serverless storefront with real auth, cart, and orders — all provisioned by Terraform.

**Architecture:** S3 hosts the static HTML/CSS/JS frontend. API Gateway HTTP API routes calls to Python 3.12 Lambda functions. DynamoDB stores users, products, cart items, and orders. JWTs (HS256, 24 h expiry) authenticate users from `localStorage`.

**Tech Stack:** Python 3.12, PyJWT 2.x, boto3 (Lambda runtime), AWS API Gateway HTTP API v2, DynamoDB on-demand, Terraform ≥ 1.5, vanilla JS + custom CSS (no framework)

---

## Reference: Project File Layout After This Plan

```
.
├── main.tf                      # existing S3 setup — do not break it
├── dynamodb.tf                  # NEW
├── iam.tf                       # NEW
├── lambda.tf                    # NEW
├── api_gateway.tf               # NEW
├── variables.tf                 # MODIFIED (add jwt_secret)
├── outputs.tf                   # MODIFIED (add api_url)
├── providers.tf                 # existing — unchanged
├── lambda/
│   ├── auth/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── products/
│   │   └── handler.py
│   ├── cart/
│   │   └── handler.py
│   ├── orders/
│   │   └── handler.py
│   └── seeder/
│       └── handler.py
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_products.py
│   ├── test_cart.py
│   └── test_orders.py
├── requirements-dev.txt
└── website/
    ├── css/
    │   └── app.css              # NEW — replaces bootstrap.css usage
    ├── js/
    │   └── api.js               # NEW — shared fetch helper + auth guard
    ├── index.html               # unchanged (redirect only)
    ├── Login.html               # MODIFIED
    ├── HomePage.html            # MODIFIED
    ├── Products.html            # MODIFIED
    ├── AccountInfo.html         # MODIFIED
    └── UsersPastOrders.html     # MODIFIED
```

---

## Task 1: Project scaffolding and dev dependencies

**Files:**
- Create: `requirements-dev.txt`
- Create: `lambda/auth/requirements.txt`
- Create: `lambda/auth/handler.py` (stub)
- Create: `lambda/products/handler.py` (stub)
- Create: `lambda/cart/handler.py` (stub)
- Create: `lambda/orders/handler.py` (stub)
- Create: `lambda/seeder/handler.py` (stub)

**Step 1: Create dev requirements**

`requirements-dev.txt`:
```
pytest>=8.0
moto[dynamodb]>=5.0
boto3>=1.34
PyJWT>=2.8
```

**Step 2: Create auth requirements**

`lambda/auth/requirements.txt`:
```
PyJWT>=2.8.0
```

**Step 3: Create stub handlers (one per file)**

Each handler stub (`lambda/auth/handler.py`, `lambda/products/handler.py`, `lambda/cart/handler.py`, `lambda/orders/handler.py`, `lambda/seeder/handler.py`):

```python
def lambda_handler(event, context):
    return {"statusCode": 200, "body": "stub"}
```

**Step 4: Install dev dependencies**

```bash
pip install -r requirements-dev.txt
```

Expected: installs pytest, moto, boto3, PyJWT.

**Step 5: Commit**

```bash
git add lambda/ requirements-dev.txt
git commit -m "feat: scaffold lambda directories and dev deps"
```

---

## Task 2: Auth Lambda handler

**Files:**
- Modify: `lambda/auth/handler.py`

### What this Lambda handles
- `POST /auth/signup` — create user, return JWT
- `POST /auth/login` — verify password, return JWT

The event format is API Gateway HTTP API payload format 2.0. The route is in `event["routeKey"]`.

**Step 1: Write the full handler**

`lambda/auth/handler.py`:
```python
import json
import os
import uuid
import hashlib
import hmac
import boto3
import jwt
from datetime import datetime, timedelta, timezone

dynamodb = boto3.resource("dynamodb")

def _table():
    return dynamodb.Table(os.environ["USERS_TABLE"])

def _hash_password(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return dk.hex()

def _make_salt() -> str:
    return uuid.uuid4().hex

def _make_token(user_id: str, name: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "name": name,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")

def _ok(body: dict) -> dict:
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }

def _err(status: int, msg: str) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": msg}),
    }

def _signup(body: dict) -> dict:
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not name or not email or not password:
        return _err(400, "name, email, and password are required")

    table = _table()
    # check duplicate email via scan (small table, acceptable for class project)
    resp = table.scan(FilterExpression=boto3.dynamodb.conditions.Attr("email").eq(email))
    if resp["Items"]:
        return _err(409, "email already registered")

    user_id = uuid.uuid4().hex
    salt = _make_salt()
    pw_hash = _hash_password(password, salt)
    table.put_item(Item={
        "userId": user_id,
        "name": name,
        "email": email,
        "passwordHash": pw_hash,
        "salt": salt,
    })
    token = _make_token(user_id, name, email)
    return _ok({"token": token, "name": name, "email": email})

def _login(body: dict) -> dict:
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        return _err(400, "email and password are required")

    table = _table()
    resp = table.scan(FilterExpression=boto3.dynamodb.conditions.Attr("email").eq(email))
    if not resp["Items"]:
        return _err(401, "invalid credentials")

    user = resp["Items"][0]
    expected = _hash_password(password, user["salt"])
    if not hmac.compare_digest(expected, user["passwordHash"]):
        return _err(401, "invalid credentials")

    token = _make_token(user["userId"], user["name"], user["email"])
    return _ok({"token": token, "name": user["name"], "email": user["email"]})

def lambda_handler(event, context):
    route = event.get("routeKey", "")
    body = json.loads(event.get("body") or "{}")

    if route == "POST /auth/signup":
        return _signup(body)
    if route == "POST /auth/login":
        return _login(body)
    return _err(404, "not found")
```

**Step 2: Commit**

```bash
git add lambda/auth/handler.py
git commit -m "feat: auth lambda handler (signup + login)"
```

---

## Task 3: Products Lambda handler

**Files:**
- Modify: `lambda/products/handler.py`

**Step 1: Write handler**

`lambda/products/handler.py`:
```python
import json
import os
import boto3

dynamodb = boto3.resource("dynamodb")

def _ok(body):
    return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}

def lambda_handler(event, context):
    table = dynamodb.Table(os.environ["PRODUCTS_TABLE"])
    resp = table.scan()
    products = sorted(resp.get("Items", []), key=lambda p: p.get("partNumber", ""))
    # convert Decimal to float for JSON serialization
    for p in products:
        if "price" in p:
            p["price"] = float(p["price"])
    return _ok(products)
```

**Step 2: Commit**

```bash
git add lambda/products/handler.py
git commit -m "feat: products lambda handler"
```

---

## Task 4: Cart Lambda handler

**Files:**
- Modify: `lambda/cart/handler.py`

The cart table has PK=userId, SK=productId.

**Step 1: Write handler**

`lambda/cart/handler.py`:
```python
import json
import os
import boto3
import jwt

dynamodb = boto3.resource("dynamodb")

def _ok(body):
    return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}

def _err(status, msg):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": msg})}

def _get_user_id(event):
    auth = (event.get("headers") or {}).get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(auth[7:], os.environ["JWT_SECRET"], algorithms=["HS256"])
        return payload["sub"]
    except Exception:
        return None

def _get_cart(user_id):
    table = dynamodb.Table(os.environ["CART_TABLE"])
    products_table = dynamodb.Table(os.environ["PRODUCTS_TABLE"])
    resp = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("userId").eq(user_id)
    )
    items = []
    for item in resp.get("Items", []):
        prod = products_table.get_item(Key={"productId": item["productId"]}).get("Item", {})
        items.append({
            "productId": item["productId"],
            "quantity": int(item.get("quantity", 1)),
            "name": prod.get("name", ""),
            "price": float(prod.get("price", 0)),
            "imageUrl": prod.get("imageUrl", ""),
            "partNumber": prod.get("partNumber", ""),
        })
    return items

def _add_to_cart(user_id, body):
    product_id = body.get("productId")
    quantity = int(body.get("quantity", 1))
    if not product_id:
        return _err(400, "productId required")
    table = dynamodb.Table(os.environ["CART_TABLE"])
    table.put_item(Item={"userId": user_id, "productId": product_id, "quantity": quantity})
    return _ok({"message": "added to cart"})

def _remove_from_cart(user_id, product_id):
    table = dynamodb.Table(os.environ["CART_TABLE"])
    table.delete_item(Key={"userId": user_id, "productId": product_id})
    return _ok({"message": "removed from cart"})

def lambda_handler(event, context):
    user_id = _get_user_id(event)
    if not user_id:
        return _err(401, "unauthorized")

    route = event.get("routeKey", "")
    if route == "GET /cart":
        return _ok(_get_cart(user_id))
    if route == "POST /cart":
        return _add_to_cart(user_id, json.loads(event.get("body") or "{}"))
    if route == "DELETE /cart/{productId}":
        product_id = (event.get("pathParameters") or {}).get("productId", "")
        return _remove_from_cart(user_id, product_id)
    return _err(404, "not found")
```

**Step 2: Commit**

```bash
git add lambda/cart/handler.py
git commit -m "feat: cart lambda handler"
```

---

## Task 5: Orders Lambda handler

**Files:**
- Modify: `lambda/orders/handler.py`

Checkout reads the user's cart, saves an order, then clears the cart.

**Step 1: Write handler**

`lambda/orders/handler.py`:
```python
import json
import os
import uuid
import boto3
import jwt
from datetime import datetime, timezone
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")

def _ok(body):
    return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}

def _err(status, msg):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": msg})}

def _get_user_id(event):
    auth = (event.get("headers") or {}).get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(auth[7:], os.environ["JWT_SECRET"], algorithms=["HS256"])
        return payload["sub"]
    except Exception:
        return None

def _checkout(user_id):
    cart_table = dynamodb.Table(os.environ["CART_TABLE"])
    products_table = dynamodb.Table(os.environ["PRODUCTS_TABLE"])
    orders_table = dynamodb.Table(os.environ["ORDERS_TABLE"])

    cart_resp = cart_table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("userId").eq(user_id)
    )
    cart_items = cart_resp.get("Items", [])
    if not cart_items:
        return _err(400, "cart is empty")

    items_snapshot = []
    total = Decimal("0")
    for item in cart_items:
        prod = products_table.get_item(Key={"productId": item["productId"]}).get("Item", {})
        qty = int(item.get("quantity", 1))
        price = Decimal(str(prod.get("price", "0")))
        items_snapshot.append({
            "productId": item["productId"],
            "name": prod.get("name", ""),
            "partNumber": prod.get("partNumber", ""),
            "price": str(price),
            "quantity": qty,
        })
        total += price * qty

    order_id = uuid.uuid4().hex
    date_str = datetime.now(timezone.utc).strftime("%B %-d, %Y")
    orders_table.put_item(Item={
        "userId": user_id,
        "orderId": order_id,
        "items": items_snapshot,
        "total": str(total),
        "date": date_str,
        "delivered": False,
    })

    # clear the cart
    with cart_table.batch_writer() as batch:
        for item in cart_items:
            batch.delete_item(Key={"userId": user_id, "productId": item["productId"]})

    return _ok({"orderId": order_id, "total": str(total), "date": date_str})

def _list_orders(user_id):
    orders_table = dynamodb.Table(os.environ["ORDERS_TABLE"])
    resp = orders_table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("userId").eq(user_id),
        ScanIndexForward=False,  # newest first
    )
    orders = []
    for o in resp.get("Items", []):
        orders.append({
            "orderId": o["orderId"],
            "total": str(o.get("total", "0")),
            "date": o.get("date", ""),
            "delivered": bool(o.get("delivered", False)),
            "items": o.get("items", []),
        })
    return _ok(orders)

def lambda_handler(event, context):
    user_id = _get_user_id(event)
    if not user_id:
        return _err(401, "unauthorized")

    route = event.get("routeKey", "")
    if route == "POST /orders":
        return _checkout(user_id)
    if route == "GET /orders":
        return _list_orders(user_id)
    return _err(404, "not found")
```

**Step 2: Commit**

```bash
git add lambda/orders/handler.py
git commit -m "feat: orders lambda handler"
```

---

## Task 6: Product seeder Lambda

**Files:**
- Modify: `lambda/seeder/handler.py`

This runs once at deploy time to populate DynamoDB with the 3 products.

**Step 1: Write handler**

`lambda/seeder/handler.py`:
```python
import os
import boto3
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")

PRODUCTS = [
    {
        "productId": "hat-001",
        "partNumber": "HAT-123",
        "name": "CloudSev Cap",
        "price": Decimal("9.99"),
        "imageUrl": "hat.png",
    },
    {
        "productId": "shirt-001",
        "partNumber": "SHIRT-123",
        "name": "CloudSev T-Shirt",
        "price": Decimal("19.99"),
        "imageUrl": "shirt.png",
    },
    {
        "productId": "shoes-001",
        "partNumber": "SHOES-123",
        "name": "CloudSev Sneakers",
        "price": Decimal("49.99"),
        "imageUrl": "shoes.png",
    },
]

def lambda_handler(event, context):
    table = dynamodb.Table(os.environ["PRODUCTS_TABLE"])
    for product in PRODUCTS:
        table.put_item(Item=product)
    print(f"Seeded {len(PRODUCTS)} products into {os.environ['PRODUCTS_TABLE']}")
    return {"statusCode": 200, "body": "seeded"}
```

**Step 2: Commit**

```bash
git add lambda/seeder/handler.py
git commit -m "feat: product seeder lambda"
```

---

## Task 7: Tests for Lambda handlers

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_auth.py`
- Create: `tests/test_products.py`
- Create: `tests/test_cart.py`
- Create: `tests/test_orders.py`

**Step 1: Write conftest.py**

`tests/conftest.py`:
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

@pytest.fixture
def aws_tables():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        # users
        client.create_table(TableName="cloudsev-users",
            KeySchema=[{"AttributeName": "userId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "userId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST")
        # products
        client.create_table(TableName="cloudsev-products",
            KeySchema=[{"AttributeName": "productId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "productId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST")
        # cart
        client.create_table(TableName="cloudsev-cart",
            KeySchema=[
                {"AttributeName": "userId", "KeyType": "HASH"},
                {"AttributeName": "productId", "KeyType": "RANGE"}
            ],
            AttributeDefinitions=[
                {"AttributeName": "userId", "AttributeType": "S"},
                {"AttributeName": "productId", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST")
        # orders
        client.create_table(TableName="cloudsev-orders",
            KeySchema=[
                {"AttributeName": "userId", "KeyType": "HASH"},
                {"AttributeName": "orderId", "KeyType": "RANGE"}
            ],
            AttributeDefinitions=[
                {"AttributeName": "userId", "AttributeType": "S"},
                {"AttributeName": "orderId", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST")
        yield
```

**Step 2: Write test_auth.py**

`tests/test_auth.py`:
```python
import json
import sys
sys.path.insert(0, "lambda/auth")
from handler import lambda_handler

def _event(route, body):
    return {"routeKey": route, "body": json.dumps(body), "headers": {}}

def test_signup_success(aws_tables):
    event = _event("POST /auth/signup", {"name": "Alice", "email": "alice@test.com", "password": "pass123"})
    resp = lambda_handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "token" in body
    assert body["email"] == "alice@test.com"

def test_signup_duplicate_email(aws_tables):
    event = _event("POST /auth/signup", {"name": "Alice", "email": "alice@test.com", "password": "pass123"})
    lambda_handler(event, None)
    resp = lambda_handler(event, None)
    assert resp["statusCode"] == 409

def test_login_success(aws_tables):
    lambda_handler(_event("POST /auth/signup", {"name": "Bob", "email": "bob@test.com", "password": "secret"}), None)
    resp = lambda_handler(_event("POST /auth/login", {"email": "bob@test.com", "password": "secret"}), None)
    assert resp["statusCode"] == 200
    assert "token" in json.loads(resp["body"])

def test_login_wrong_password(aws_tables):
    lambda_handler(_event("POST /auth/signup", {"name": "Bob", "email": "bob@test.com", "password": "secret"}), None)
    resp = lambda_handler(_event("POST /auth/login", {"email": "bob@test.com", "password": "wrong"}), None)
    assert resp["statusCode"] == 401

def test_login_unknown_email(aws_tables):
    resp = lambda_handler(_event("POST /auth/login", {"email": "ghost@test.com", "password": "x"}), None)
    assert resp["statusCode"] == 401
```

**Step 3: Write test_products.py**

`tests/test_products.py`:
```python
import json
import sys
import boto3
from decimal import Decimal
sys.path.insert(0, "lambda/products")
from handler import lambda_handler

def test_list_products_empty(aws_tables):
    resp = lambda_handler({}, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == []

def test_list_products_returns_items(aws_tables):
    table = boto3.resource("dynamodb", region_name="us-east-1").Table("cloudsev-products")
    table.put_item(Item={"productId": "p1", "name": "Hat", "price": Decimal("9.99"), "partNumber": "HAT-1"})
    resp = lambda_handler({}, None)
    body = json.loads(resp["body"])
    assert len(body) == 1
    assert body[0]["name"] == "Hat"
    assert body[0]["price"] == 9.99
```

**Step 4: Write test_cart.py**

`tests/test_cart.py`:
```python
import json
import sys
import boto3
from decimal import Decimal
sys.path.insert(0, "lambda/auth")
from handler import lambda_handler as auth_handler
sys.path.insert(0, "lambda/cart")
from handler import lambda_handler as cart_handler

def _signup_token(aws_tables):
    resp = auth_handler({"routeKey": "POST /auth/signup", "body": json.dumps({"name": "T", "email": "t@t.com", "password": "pw"}), "headers": {}}, None)
    return json.loads(resp["body"])["token"]

def _auth_event(route, token, body=None, path_params=None):
    return {
        "routeKey": route,
        "headers": {"authorization": f"Bearer {token}"},
        "body": json.dumps(body) if body else None,
        "pathParameters": path_params or {},
    }

def test_get_empty_cart(aws_tables):
    token = _signup_token(aws_tables)
    resp = cart_handler(_auth_event("GET /cart", token), None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == []

def test_add_and_get_cart(aws_tables):
    table = boto3.resource("dynamodb", region_name="us-east-1").Table("cloudsev-products")
    table.put_item(Item={"productId": "hat-001", "name": "Hat", "price": Decimal("9.99"), "partNumber": "HAT-1", "imageUrl": "hat.png"})
    token = _signup_token(aws_tables)
    cart_handler(_auth_event("POST /cart", token, {"productId": "hat-001", "quantity": 2}), None)
    resp = cart_handler(_auth_event("GET /cart", token), None)
    items = json.loads(resp["body"])
    assert len(items) == 1
    assert items[0]["productId"] == "hat-001"
    assert items[0]["quantity"] == 2

def test_remove_from_cart(aws_tables):
    table = boto3.resource("dynamodb", region_name="us-east-1").Table("cloudsev-products")
    table.put_item(Item={"productId": "hat-001", "name": "Hat", "price": Decimal("9.99"), "partNumber": "HAT-1", "imageUrl": "hat.png"})
    token = _signup_token(aws_tables)
    cart_handler(_auth_event("POST /cart", token, {"productId": "hat-001"}), None)
    cart_handler(_auth_event("DELETE /cart/{productId}", token, path_params={"productId": "hat-001"}), None)
    resp = cart_handler(_auth_event("GET /cart", token), None)
    assert json.loads(resp["body"]) == []

def test_unauthorized_cart(aws_tables):
    resp = cart_handler({"routeKey": "GET /cart", "headers": {}, "body": None, "pathParameters": {}}, None)
    assert resp["statusCode"] == 401
```

**Step 5: Write test_orders.py**

`tests/test_orders.py`:
```python
import json
import sys
import boto3
from decimal import Decimal
sys.path.insert(0, "lambda/auth")
from handler import lambda_handler as auth_handler
sys.path.insert(0, "lambda/cart")
from handler import lambda_handler as cart_handler
sys.path.insert(0, "lambda/orders")
from handler import lambda_handler as orders_handler

def _signup_token():
    resp = auth_handler({"routeKey": "POST /auth/signup", "body": json.dumps({"name": "U", "email": "u@u.com", "password": "pw"}), "headers": {}}, None)
    return json.loads(resp["body"])["token"]

def _event(route, token, body=None):
    return {"routeKey": route, "headers": {"authorization": f"Bearer {token}"}, "body": json.dumps(body) if body else None, "pathParameters": {}}

def test_checkout_empty_cart(aws_tables):
    token = _signup_token()
    resp = orders_handler(_event("POST /orders", token), None)
    assert resp["statusCode"] == 400

def test_checkout_creates_order_and_clears_cart(aws_tables):
    table = boto3.resource("dynamodb", region_name="us-east-1").Table("cloudsev-products")
    table.put_item(Item={"productId": "shirt-001", "name": "Shirt", "price": Decimal("19.99"), "partNumber": "SHIRT-1", "imageUrl": "shirt.png"})
    token = _signup_token()
    cart_handler({"routeKey": "POST /cart", "headers": {"authorization": f"Bearer {token}"}, "body": json.dumps({"productId": "shirt-001", "quantity": 1}), "pathParameters": {}}, None)
    resp = orders_handler(_event("POST /orders", token), None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "orderId" in body
    assert body["total"] == "19.99"
    # cart should be empty
    cart_resp = cart_handler({"routeKey": "GET /cart", "headers": {"authorization": f"Bearer {token}"}, "body": None, "pathParameters": {}}, None)
    assert json.loads(cart_resp["body"]) == []

def test_list_orders(aws_tables):
    table = boto3.resource("dynamodb", region_name="us-east-1").Table("cloudsev-products")
    table.put_item(Item={"productId": "shoes-001", "name": "Shoes", "price": Decimal("49.99"), "partNumber": "SHOES-1", "imageUrl": "shoes.png"})
    token = _signup_token()
    cart_handler({"routeKey": "POST /cart", "headers": {"authorization": f"Bearer {token}"}, "body": json.dumps({"productId": "shoes-001"}), "pathParameters": {}}, None)
    orders_handler(_event("POST /orders", token), None)
    resp = orders_handler(_event("GET /orders", token), None)
    orders = json.loads(resp["body"])
    assert len(orders) == 1
    assert orders[0]["total"] == "49.99"
```

**Step 6: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests pass.

**Step 7: Commit**

```bash
git add tests/
git commit -m "test: add lambda handler tests with moto"
```

---

## Task 8: Terraform — DynamoDB tables

**Files:**
- Create: `dynamodb.tf`

**Step 1: Write dynamodb.tf**

```hcl
resource "aws_dynamodb_table" "users" {
  name         = "cloudsev-users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"

  attribute {
    name = "userId"
    type = "S"
  }

  tags = { Project = "cloudsev", ManagedBy = "Terraform" }
}

resource "aws_dynamodb_table" "products" {
  name         = "cloudsev-products"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "productId"

  attribute {
    name = "productId"
    type = "S"
  }

  tags = { Project = "cloudsev", ManagedBy = "Terraform" }
}

resource "aws_dynamodb_table" "cart" {
  name         = "cloudsev-cart"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"
  range_key    = "productId"

  attribute {
    name = "userId"
    type = "S"
  }
  attribute {
    name = "productId"
    type = "S"
  }

  tags = { Project = "cloudsev", ManagedBy = "Terraform" }
}

resource "aws_dynamodb_table" "orders" {
  name         = "cloudsev-orders"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"
  range_key    = "orderId"

  attribute {
    name = "userId"
    type = "S"
  }
  attribute {
    name = "orderId"
    type = "S"
  }

  tags = { Project = "cloudsev", ManagedBy = "Terraform" }
}
```

**Step 2: Commit**

```bash
git add dynamodb.tf
git commit -m "feat: terraform dynamodb tables"
```

---

## Task 9: Terraform — IAM role for Lambda

**Files:**
- Create: `iam.tf`

**Step 1: Write iam.tf**

```hcl
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_exec" {
  name               = "cloudsev-lambda-exec"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = { Project = "cloudsev", ManagedBy = "Terraform" }
}

# Basic execution (CloudWatch logs)
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# DynamoDB access for all cloudsev tables
data "aws_iam_policy_document" "dynamodb_access" {
  statement {
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:BatchWriteItem",
    ]
    resources = [
      aws_dynamodb_table.users.arn,
      aws_dynamodb_table.products.arn,
      aws_dynamodb_table.cart.arn,
      aws_dynamodb_table.orders.arn,
    ]
  }
}

resource "aws_iam_role_policy" "dynamodb_access" {
  name   = "cloudsev-dynamodb-access"
  role   = aws_iam_role.lambda_exec.id
  policy = data.aws_iam_policy_document.dynamodb_access.json
}
```

**Step 2: Commit**

```bash
git add iam.tf
git commit -m "feat: terraform iam role for lambda"
```

---

## Task 10: Terraform — Lambda functions

**Files:**
- Create: `lambda.tf`
- Modify: `variables.tf` (add jwt_secret)

**Step 1: Add jwt_secret variable to variables.tf**

Append to `variables.tf`:
```hcl
variable "jwt_secret" {
  description = "Secret key used to sign and verify JWTs. Keep this private."
  type        = string
  sensitive   = true
}
```

**Step 2: Write lambda.tf**

```hcl
# ---------------------------------------------------------------
# Install PyJWT for auth lambda (pure Python, cross-platform safe)
# ---------------------------------------------------------------
resource "null_resource" "install_auth_deps" {
  triggers = {
    req_hash = filemd5("${path.module}/lambda/auth/requirements.txt")
  }
  provisioner "local-exec" {
    command = "pip install -r ${path.module}/lambda/auth/requirements.txt -t ${path.module}/lambda/auth/ --quiet --upgrade"
  }
}

# ---------------------------------------------------------------
# Zip archives
# ---------------------------------------------------------------
data "archive_file" "auth_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/auth"
  output_path = "${path.module}/lambda/auth.zip"
  excludes    = ["requirements.txt"]
  depends_on  = [null_resource.install_auth_deps]
}

data "archive_file" "products_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/products"
  output_path = "${path.module}/lambda/products.zip"
}

data "archive_file" "cart_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/cart"
  output_path = "${path.module}/lambda/cart.zip"
  depends_on  = [null_resource.install_auth_deps]  # cart shares JWT dep via auth layer approach
}

data "archive_file" "orders_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/orders"
  output_path = "${path.module}/lambda/orders.zip"
  depends_on  = [null_resource.install_auth_deps]
}

data "archive_file" "seeder_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/seeder"
  output_path = "${path.module}/lambda/seeder.zip"
}
```

> **Note:** cart and orders also need PyJWT. Before running `terraform apply`, run:
> ```bash
> pip install PyJWT>=2.8.0 -t lambda/cart/ --quiet
> pip install PyJWT>=2.8.0 -t lambda/orders/ --quiet
> ```
> Add a `requirements.txt` to each:

`lambda/cart/requirements.txt`:
```
PyJWT>=2.8.0
```

`lambda/orders/requirements.txt`:
```
PyJWT>=2.8.0
```

Then continue `lambda.tf`:

```hcl
resource "null_resource" "install_cart_deps" {
  triggers = { req_hash = filemd5("${path.module}/lambda/cart/requirements.txt") }
  provisioner "local-exec" {
    command = "pip install -r ${path.module}/lambda/cart/requirements.txt -t ${path.module}/lambda/cart/ --quiet --upgrade"
  }
}

resource "null_resource" "install_orders_deps" {
  triggers = { req_hash = filemd5("${path.module}/lambda/orders/requirements.txt") }
  provisioner "local-exec" {
    command = "pip install -r ${path.module}/lambda/orders/requirements.txt -t ${path.module}/lambda/orders/ --quiet --upgrade"
  }
}

# Recreate zips with correct depends_on
data "archive_file" "cart_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/cart"
  output_path = "${path.module}/lambda/cart.zip"
  excludes    = ["requirements.txt"]
  depends_on  = [null_resource.install_cart_deps]
}

data "archive_file" "orders_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/orders"
  output_path = "${path.module}/lambda/orders.zip"
  excludes    = ["requirements.txt"]
  depends_on  = [null_resource.install_orders_deps]
}

# ---------------------------------------------------------------
# Lambda functions
# ---------------------------------------------------------------
locals {
  lambda_env_base = {
    USERS_TABLE    = aws_dynamodb_table.users.name
    PRODUCTS_TABLE = aws_dynamodb_table.products.name
    CART_TABLE     = aws_dynamodb_table.cart.name
    ORDERS_TABLE   = aws_dynamodb_table.orders.name
    JWT_SECRET     = var.jwt_secret
  }
}

resource "aws_lambda_function" "auth" {
  filename         = data.archive_file.auth_zip.output_path
  function_name    = "cloudsev-auth"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.auth_zip.output_base64sha256
  timeout          = 15
  environment { variables = local.lambda_env_base }
  tags = { Project = "cloudsev" }
}

resource "aws_lambda_function" "products" {
  filename         = data.archive_file.products_zip.output_path
  function_name    = "cloudsev-products"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.products_zip.output_base64sha256
  timeout          = 10
  environment { variables = local.lambda_env_base }
  tags = { Project = "cloudsev" }
}

resource "aws_lambda_function" "cart" {
  filename         = data.archive_file.cart_zip.output_path
  function_name    = "cloudsev-cart"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.cart_zip.output_base64sha256
  timeout          = 10
  environment { variables = local.lambda_env_base }
  tags = { Project = "cloudsev" }
}

resource "aws_lambda_function" "orders" {
  filename         = data.archive_file.orders_zip.output_path
  function_name    = "cloudsev-orders"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.orders_zip.output_base64sha256
  timeout          = 15
  environment { variables = local.lambda_env_base }
  tags = { Project = "cloudsev" }
}

resource "aws_lambda_function" "seeder" {
  filename         = data.archive_file.seeder_zip.output_path
  function_name    = "cloudsev-seeder"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.seeder_zip.output_base64sha256
  timeout          = 30
  environment {
    variables = {
      PRODUCTS_TABLE = aws_dynamodb_table.products.name
    }
  }
  tags = { Project = "cloudsev" }
}
```

**Step 3: Commit**

```bash
git add lambda.tf variables.tf lambda/cart/requirements.txt lambda/orders/requirements.txt
git commit -m "feat: terraform lambda functions"
```

---

## Task 11: Terraform — API Gateway HTTP API

**Files:**
- Create: `api_gateway.tf`

**Step 1: Write api_gateway.tf**

```hcl
resource "aws_apigatewayv2_api" "cloudsev" {
  name          = "cloudsev-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "DELETE", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization"]
    max_age       = 300
  }

  tags = { Project = "cloudsev", ManagedBy = "Terraform" }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.cloudsev.id
  name        = "$default"
  auto_deploy = true
}

# ---------------------------------------------------------------
# Lambda integrations
# ---------------------------------------------------------------
resource "aws_apigatewayv2_integration" "auth" {
  api_id                 = aws_apigatewayv2_api.cloudsev.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.auth.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "products" {
  api_id                 = aws_apigatewayv2_api.cloudsev.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.products.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "cart" {
  api_id                 = aws_apigatewayv2_api.cloudsev.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.cart.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "orders" {
  api_id                 = aws_apigatewayv2_api.cloudsev.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.orders.invoke_arn
  payload_format_version = "2.0"
}

# ---------------------------------------------------------------
# Routes
# ---------------------------------------------------------------
resource "aws_apigatewayv2_route" "signup" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "POST /auth/signup"
  target    = "integrations/${aws_apigatewayv2_integration.auth.id}"
}

resource "aws_apigatewayv2_route" "login" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "POST /auth/login"
  target    = "integrations/${aws_apigatewayv2_integration.auth.id}"
}

resource "aws_apigatewayv2_route" "products_get" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "GET /products"
  target    = "integrations/${aws_apigatewayv2_integration.products.id}"
}

resource "aws_apigatewayv2_route" "cart_get" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "GET /cart"
  target    = "integrations/${aws_apigatewayv2_integration.cart.id}"
}

resource "aws_apigatewayv2_route" "cart_post" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "POST /cart"
  target    = "integrations/${aws_apigatewayv2_integration.cart.id}"
}

resource "aws_apigatewayv2_route" "cart_delete" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "DELETE /cart/{productId}"
  target    = "integrations/${aws_apigatewayv2_integration.cart.id}"
}

resource "aws_apigatewayv2_route" "orders_post" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "POST /orders"
  target    = "integrations/${aws_apigatewayv2_integration.orders.id}"
}

resource "aws_apigatewayv2_route" "orders_get" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "GET /orders"
  target    = "integrations/${aws_apigatewayv2_integration.orders.id}"
}

# ---------------------------------------------------------------
# Lambda permissions — allow API Gateway to invoke each function
# ---------------------------------------------------------------
resource "aws_lambda_permission" "auth" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auth.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.cloudsev.execution_arn}/*/*"
}

resource "aws_lambda_permission" "products" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.products.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.cloudsev.execution_arn}/*/*"
}

resource "aws_lambda_permission" "cart" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cart.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.cloudsev.execution_arn}/*/*"
}

resource "aws_lambda_permission" "orders" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.orders.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.cloudsev.execution_arn}/*/*"
}

# ---------------------------------------------------------------
# Seeder — invoke once after DynamoDB + Lambda are created
# ---------------------------------------------------------------
resource "null_resource" "seed_products" {
  triggers = {
    seeder_version = aws_lambda_function.seeder.source_code_hash
    table_created  = aws_dynamodb_table.products.id
  }

  provisioner "local-exec" {
    command = "aws lambda invoke --function-name ${aws_lambda_function.seeder.function_name} --region ${var.aws_region} /dev/null"
  }

  depends_on = [
    aws_lambda_function.seeder,
    aws_dynamodb_table.products,
    aws_iam_role_policy.dynamodb_access,
  ]
}
```

**Step 2: Update outputs.tf — add API URL**

Append to `outputs.tf`:
```hcl
output "api_url" {
  description = "Base URL for the CloudSev API (API Gateway HTTP API)."
  value       = aws_apigatewayv2_api.cloudsev.api_endpoint
}
```

**Step 3: Commit**

```bash
git add api_gateway.tf outputs.tf
git commit -m "feat: terraform api gateway http api + seeder"
```

---

## Task 12: Frontend — CSS design system

**Files:**
- Create: `website/css/app.css`

Replace the Bootstrap 2 dependency entirely. Design language: deep navy background, gold accents, clean sans-serif, card-based layout.

**Step 1: Write app.css**

```css
/* ============================================================
   CloudSev Design System
   ============================================================ */

:root {
  --bg:          #0a0e1a;
  --surface:     #141929;
  --surface-2:   #1e2540;
  --border:      #2a3250;
  --gold:        #f0a500;
  --gold-hover:  #ffc840;
  --text:        #e8eaf6;
  --text-muted:  #8892b0;
  --success:     #4caf82;
  --danger:      #e05263;
  --radius:      12px;
  --radius-sm:   6px;
  --shadow:      0 4px 24px rgba(0,0,0,0.4);
  --transition:  0.18s ease;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { font-size: 16px; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  min-height: 100vh;
  line-height: 1.6;
}

/* ── Layout ── */
.page-center {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem 1rem;
}

.container {
  width: 100%;
  max-width: 1100px;
  margin: 0 auto;
  padding: 0 1.5rem;
}

/* ── Card ── */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 2.5rem;
  width: 100%;
  max-width: 460px;
}

.card-wide { max-width: 860px; }

.card-header {
  text-align: center;
  margin-bottom: 2rem;
}

.card-header h1 {
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: -0.5px;
  color: var(--text);
}

.card-header p {
  color: var(--text-muted);
  margin-top: 0.4rem;
  font-size: 0.95rem;
}

.logo-accent { color: var(--gold); }

/* ── Navigation bar ── */
.navbar {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 1.5rem;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 100;
}

.navbar-brand {
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--text);
  text-decoration: none;
}

.navbar-brand span { color: var(--gold); }

.navbar-links { display: flex; align-items: center; gap: 0.25rem; }

.navbar-links a, .navbar-links button {
  color: var(--text-muted);
  text-decoration: none;
  font-size: 0.9rem;
  padding: 0.4rem 0.75rem;
  border-radius: var(--radius-sm);
  border: none;
  background: none;
  cursor: pointer;
  transition: color var(--transition), background var(--transition);
}

.navbar-links a:hover, .navbar-links button:hover {
  color: var(--text);
  background: var(--surface-2);
}

.cart-badge {
  background: var(--gold);
  color: #000;
  font-size: 0.7rem;
  font-weight: 700;
  border-radius: 999px;
  padding: 1px 6px;
  margin-left: 4px;
  vertical-align: middle;
}

/* ── Forms ── */
.form-group { margin-bottom: 1.25rem; }

label {
  display: block;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-muted);
  margin-bottom: 0.4rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

input[type="text"],
input[type="email"],
input[type="password"] {
  width: 100%;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  font-size: 1rem;
  padding: 0.65rem 0.9rem;
  outline: none;
  transition: border-color var(--transition), box-shadow var(--transition);
}

input:focus {
  border-color: var(--gold);
  box-shadow: 0 0 0 3px rgba(240,165,0,0.15);
}

/* ── Buttons ── */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  padding: 0.65rem 1.4rem;
  border-radius: var(--radius-sm);
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: background var(--transition), transform var(--transition), opacity var(--transition);
  text-decoration: none;
}

.btn:active { transform: translateY(1px); }

.btn-primary {
  background: var(--gold);
  color: #000;
  width: 100%;
  padding: 0.8rem;
  font-size: 1rem;
  margin-top: 0.5rem;
}

.btn-primary:hover { background: var(--gold-hover); }

.btn-secondary {
  background: var(--surface-2);
  color: var(--text);
  border: 1px solid var(--border);
}

.btn-secondary:hover { background: var(--border); }

.btn-danger {
  background: transparent;
  color: var(--danger);
  border: 1px solid var(--danger);
  padding: 0.3rem 0.7rem;
  font-size: 0.8rem;
}

.btn-danger:hover { background: var(--danger); color: #fff; }

.btn-sm { padding: 0.4rem 0.9rem; font-size: 0.85rem; }

.btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Auth toggle ── */
.auth-toggle {
  text-align: center;
  margin-top: 1.5rem;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.auth-toggle a {
  color: var(--gold);
  text-decoration: none;
  font-weight: 600;
  cursor: pointer;
}

.auth-toggle a:hover { color: var(--gold-hover); }

/* ── Home nav cards ── */
.nav-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  margin-top: 0.5rem;
}

.nav-card {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.5rem;
  text-align: center;
  text-decoration: none;
  color: var(--text);
  transition: border-color var(--transition), transform var(--transition), box-shadow var(--transition);
  cursor: pointer;
}

.nav-card:hover {
  border-color: var(--gold);
  transform: translateY(-3px);
  box-shadow: 0 8px 24px rgba(240,165,0,0.12);
}

.nav-card-icon { font-size: 2rem; margin-bottom: 0.75rem; }
.nav-card-label { font-weight: 600; font-size: 0.95rem; }
.nav-card-sub { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.3rem; }

/* ── Product grid ── */
.products-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 1.5rem;
  margin-top: 1.5rem;
}

.product-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  transition: border-color var(--transition), transform var(--transition);
}

.product-card:hover {
  border-color: var(--gold);
  transform: translateY(-2px);
}

.product-card img {
  width: 100%;
  height: 180px;
  object-fit: cover;
  background: var(--surface-2);
}

.product-card-body { padding: 1.2rem; }
.product-card-name { font-weight: 700; font-size: 1rem; }
.product-card-part { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem; }
.product-card-price { font-size: 1.3rem; font-weight: 700; color: var(--gold); margin: 0.75rem 0; }

/* ── Cart panel ── */
.cart-panel {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.5rem;
  margin-top: 2rem;
}

.cart-panel h2 { font-size: 1.1rem; margin-bottom: 1rem; }

.cart-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--border);
}

.cart-item:last-child { border-bottom: none; }
.cart-item-name { font-weight: 600; }
.cart-item-meta { font-size: 0.85rem; color: var(--text-muted); }
.cart-total { font-size: 1.1rem; font-weight: 700; color: var(--gold); margin-top: 1rem; }

/* ── Tables ── */
.table-wrap { overflow-x: auto; }

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.95rem;
}

th {
  text-align: left;
  padding: 0.75rem 1rem;
  background: var(--surface-2);
  color: var(--text-muted);
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border);
}

td {
  padding: 0.9rem 1rem;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}

tr:last-child td { border-bottom: none; }
tr:hover td { background: rgba(255,255,255,0.02); }

/* ── Badges ── */
.badge {
  display: inline-block;
  padding: 0.25rem 0.7rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.badge-success { background: rgba(76,175,130,0.15); color: var(--success); }
.badge-pending { background: rgba(240,165,0,0.15); color: var(--gold); }

/* ── Info list ── */
.info-list { list-style: none; }

.info-list li {
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--border);
  display: flex;
  gap: 1rem;
  font-size: 0.95rem;
}

.info-list li:last-child { border-bottom: none; }
.info-list li strong { color: var(--text-muted); min-width: 80px; font-weight: 500; }

/* ── Page header ── */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.page-header h1 { font-size: 1.6rem; font-weight: 700; }

/* ── Alert / messages ── */
.alert {
  padding: 0.75rem 1rem;
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
  margin-bottom: 1rem;
}

.alert-error { background: rgba(224,82,99,0.12); color: var(--danger); border: 1px solid rgba(224,82,99,0.3); }
.alert-success { background: rgba(76,175,130,0.12); color: var(--success); border: 1px solid rgba(76,175,130,0.3); }

/* ── Loading spinner ── */
.spinner {
  display: inline-block;
  width: 20px; height: 20px;
  border: 2px solid var(--border);
  border-top-color: var(--gold);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  vertical-align: middle;
}

@keyframes spin { to { transform: rotate(360deg); } }

.loading-state {
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
}

/* ── Empty state ── */
.empty-state {
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
}

.empty-state-icon { font-size: 3rem; margin-bottom: 1rem; }

/* ── Responsive ── */
@media (max-width: 600px) {
  .card { padding: 1.5rem; }
  .nav-cards { grid-template-columns: 1fr 1fr; }
  .products-grid { grid-template-columns: 1fr; }
  .page-header { flex-direction: column; align-items: flex-start; }
}
```

**Step 2: Commit**

```bash
git add website/css/app.css
git commit -m "feat: custom css design system (dark/gold theme)"
```

---

## Task 13: Frontend — shared JS (api.js)

**Files:**
- Create: `website/js/api.js`

This file provides: auth guard, API base URL (reads from `localStorage`), and fetch helpers used by every page.

**Step 1: Write api.js**

```javascript
// ──────────────────────────────────────────────────────────────
// api.js  —  shared fetch helper + auth utilities
// Set window.API_BASE before including this script, or set it
// in localStorage under "api_url" after first deploy.
// ──────────────────────────────────────────────────────────────

const API_BASE = localStorage.getItem("api_url") || window.API_BASE || "";

function getToken() {
  return localStorage.getItem("token");
}

function getUser() {
  const token = getToken();
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    if (payload.exp * 1000 < Date.now()) {
      localStorage.removeItem("token");
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

function requireAuth() {
  if (!getUser()) {
    window.location.href = "Login.html";
    return false;
  }
  return true;
}

function logout() {
  localStorage.removeItem("token");
  window.location.href = "Login.html";
}

async function apiCall(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const opts = { method, headers };
  if (body !== undefined) opts.body = JSON.stringify(body);

  const res = await fetch(`${API_BASE}${path}`, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

const api = {
  signup: (name, email, password) =>
    apiCall("POST", "/auth/signup", { name, email, password }),
  login: (email, password) =>
    apiCall("POST", "/auth/login", { email, password }),
  products: () => apiCall("GET", "/products"),
  getCart: () => apiCall("GET", "/cart"),
  addToCart: (productId, quantity = 1) =>
    apiCall("POST", "/cart", { productId, quantity }),
  removeFromCart: (productId) =>
    apiCall("DELETE", `/cart/${productId}`),
  checkout: () => apiCall("POST", "/orders"),
  getOrders: () => apiCall("GET", "/orders"),
};
```

**Step 2: Commit**

```bash
git add website/js/api.js
git commit -m "feat: shared api.js for frontend"
```

---

## Task 14: Frontend — Login.html

**Files:**
- Modify: `website/Login.html`

**Step 1: Rewrite Login.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>CloudSev | Login</title>
  <link rel="stylesheet" href="css/app.css" />
</head>
<body>
<div class="page-center">
  <div class="card">
    <div class="card-header">
      <h1><span class="logo-accent">Cloud</span>Sev</h1>
      <p id="form-subtitle">Sign in to your account</p>
    </div>

    <div id="alert" class="alert alert-error" style="display:none"></div>

    <!-- LOGIN FORM -->
    <form id="login-form">
      <div class="form-group">
        <label for="email">Email</label>
        <input id="email" type="email" placeholder="you@example.com" required />
      </div>
      <div class="form-group">
        <label for="password">Password</label>
        <input id="password" type="password" placeholder="••••••••" required />
      </div>
      <button type="submit" class="btn btn-primary" id="submit-btn">Sign In</button>
    </form>

    <!-- SIGNUP FORM (hidden by default) -->
    <form id="signup-form" style="display:none">
      <div class="form-group">
        <label for="name">Full Name</label>
        <input id="name" type="text" placeholder="Jane Doe" required />
      </div>
      <div class="form-group">
        <label for="email2">Email</label>
        <input id="email2" type="email" placeholder="you@example.com" required />
      </div>
      <div class="form-group">
        <label for="password2">Password</label>
        <input id="password2" type="password" placeholder="At least 6 characters" required minlength="6" />
      </div>
      <button type="submit" class="btn btn-primary" id="signup-btn">Create Account</button>
    </form>

    <div class="auth-toggle">
      <span id="toggle-text">Don't have an account?</span>
      <a id="toggle-link" onclick="toggleForm()">Sign up</a>
    </div>
  </div>
</div>

<script src="js/api.js"></script>
<script>
  // If already logged in, skip to home
  if (getUser()) window.location.href = "HomePage.html";

  let isLogin = true;

  function toggleForm() {
    isLogin = !isLogin;
    document.getElementById("login-form").style.display = isLogin ? "" : "none";
    document.getElementById("signup-form").style.display = isLogin ? "none" : "";
    document.getElementById("form-subtitle").textContent = isLogin ? "Sign in to your account" : "Create a new account";
    document.getElementById("toggle-text").textContent = isLogin ? "Don't have an account?" : "Already have an account?";
    document.getElementById("toggle-link").textContent = isLogin ? "Sign up" : "Sign in";
    document.getElementById("alert").style.display = "none";
  }

  function showAlert(msg) {
    const el = document.getElementById("alert");
    el.textContent = msg;
    el.style.display = "";
  }

  function saveAndRedirect(data) {
    localStorage.setItem("token", data.token);
    window.location.href = "HomePage.html";
  }

  document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("submit-btn");
    btn.disabled = true;
    btn.textContent = "Signing in…";
    try {
      const data = await api.login(
        document.getElementById("email").value,
        document.getElementById("password").value
      );
      saveAndRedirect(data);
    } catch (err) {
      showAlert(err.message);
      btn.disabled = false;
      btn.textContent = "Sign In";
    }
  });

  document.getElementById("signup-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("signup-btn");
    btn.disabled = true;
    btn.textContent = "Creating account…";
    try {
      const data = await api.signup(
        document.getElementById("name").value,
        document.getElementById("email2").value,
        document.getElementById("password2").value
      );
      saveAndRedirect(data);
    } catch (err) {
      showAlert(err.message);
      btn.disabled = false;
      btn.textContent = "Create Account";
    }
  });
</script>
</body>
</html>
```

**Step 2: Commit**

```bash
git add website/Login.html
git commit -m "feat: login page with real auth"
```

---

## Task 15: Frontend — HomePage.html

**Files:**
- Modify: `website/HomePage.html`

**Step 1: Rewrite HomePage.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>CloudSev | Home</title>
  <link rel="stylesheet" href="css/app.css" />
</head>
<body>
<nav class="navbar">
  <a class="navbar-brand" href="HomePage.html"><span>Cloud</span>Sev</a>
  <div class="navbar-links">
    <button onclick="logout()">Logout</button>
  </div>
</nav>

<div class="container" style="padding-top: 3rem; padding-bottom: 3rem;">
  <div style="text-align:center; margin-bottom: 2.5rem;">
    <h1 style="font-size:2rem; font-weight:700;">Welcome back, <span class="logo-accent" id="user-name">…</span></h1>
    <p style="color:var(--text-muted); margin-top:0.5rem;">What would you like to do today?</p>
  </div>

  <div class="nav-cards" style="max-width:720px; margin:0 auto;">
    <a class="nav-card" href="Products.html">
      <div class="nav-card-icon">🛍️</div>
      <div class="nav-card-label">Browse Products</div>
      <div class="nav-card-sub">Shop our catalog</div>
    </a>
    <a class="nav-card" href="Products.html#cart">
      <div class="nav-card-icon">🛒</div>
      <div class="nav-card-label">Your Cart</div>
      <div class="nav-card-sub" id="cart-sub">Loading…</div>
    </a>
    <a class="nav-card" href="UsersPastOrders.html">
      <div class="nav-card-icon">📦</div>
      <div class="nav-card-label">Past Orders</div>
      <div class="nav-card-sub">Order history</div>
    </a>
    <a class="nav-card" href="AccountInfo.html">
      <div class="nav-card-icon">👤</div>
      <div class="nav-card-label">Account</div>
      <div class="nav-card-sub">Your profile</div>
    </a>
  </div>
</div>

<script src="js/api.js"></script>
<script>
  if (!requireAuth()) throw new Error("redirecting");
  const user = getUser();
  document.getElementById("user-name").textContent = user.name;

  api.getCart().then(items => {
    const count = items.reduce((s, i) => s + i.quantity, 0);
    document.getElementById("cart-sub").textContent =
      count === 0 ? "Your cart is empty" : `${count} item${count !== 1 ? "s" : ""} in cart`;
  }).catch(() => {
    document.getElementById("cart-sub").textContent = "View cart";
  });
</script>
</body>
</html>
```

**Step 2: Commit**

```bash
git add website/HomePage.html
git commit -m "feat: homepage with dynamic greeting + cart count"
```

---

## Task 16: Frontend — Products.html

**Files:**
- Modify: `website/Products.html`

**Step 1: Rewrite Products.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>CloudSev | Products</title>
  <link rel="stylesheet" href="css/app.css" />
</head>
<body>
<nav class="navbar">
  <a class="navbar-brand" href="HomePage.html"><span>Cloud</span>Sev</a>
  <div class="navbar-links">
    <a href="UsersPastOrders.html">Orders</a>
    <a href="AccountInfo.html">Account</a>
    <a href="#cart">Cart <span class="cart-badge" id="cart-count">0</span></a>
    <button onclick="logout()">Logout</button>
  </div>
</nav>

<div class="container" style="padding-top:2rem; padding-bottom:3rem;">
  <div class="page-header">
    <h1>Products</h1>
    <a href="HomePage.html" class="btn btn-secondary btn-sm">← Home</a>
  </div>

  <div id="alert" class="alert alert-error" style="display:none"></div>
  <div id="alert-success" class="alert alert-success" style="display:none"></div>

  <div id="products-loading" class="loading-state">
    <div class="spinner"></div>
    <p style="margin-top:1rem;">Loading products…</p>
  </div>
  <div id="products-grid" class="products-grid" style="display:none"></div>

  <!-- CART PANEL -->
  <div id="cart" class="cart-panel" style="display:none">
    <h2>🛒 Your Cart</h2>
    <div id="cart-items"></div>
    <div class="cart-total" id="cart-total" style="display:none"></div>
    <div style="margin-top:1rem; display:flex; gap:0.75rem; flex-wrap:wrap;">
      <button class="btn btn-primary" style="width:auto;" onclick="checkout()" id="checkout-btn">Checkout</button>
      <a href="UsersPastOrders.html" class="btn btn-secondary btn-sm">View Orders</a>
    </div>
  </div>
</div>

<script src="js/api.js"></script>
<script>
  if (!requireAuth()) throw new Error("redirecting");

  let cartItems = [];

  function renderCart() {
    const count = cartItems.reduce((s, i) => s + i.quantity, 0);
    document.getElementById("cart-count").textContent = count;
    const panel = document.getElementById("cart");
    const itemsEl = document.getElementById("cart-items");
    const totalEl = document.getElementById("cart-total");

    if (count === 0) {
      panel.style.display = "none";
      return;
    }
    panel.style.display = "";
    let total = 0;
    itemsEl.innerHTML = cartItems.map(item => {
      total += item.price * item.quantity;
      return `<div class="cart-item">
        <div>
          <div class="cart-item-name">${item.name}</div>
          <div class="cart-item-meta">${item.partNumber} · qty ${item.quantity}</div>
        </div>
        <div style="display:flex; align-items:center; gap:1rem;">
          <span style="font-weight:700; color:var(--gold);">$${(item.price * item.quantity).toFixed(2)}</span>
          <button class="btn btn-danger" onclick="removeItem('${item.productId}')">✕</button>
        </div>
      </div>`;
    }).join("");
    totalEl.style.display = "";
    totalEl.textContent = `Total: $${total.toFixed(2)}`;
  }

  async function loadProducts() {
    try {
      const products = await api.products();
      document.getElementById("products-loading").style.display = "none";
      const grid = document.getElementById("products-grid");
      grid.style.display = "";
      grid.innerHTML = products.map(p => `
        <div class="product-card">
          <img src="${p.imageUrl}" alt="${p.name}" onerror="this.style.background='var(--surface-2)'" />
          <div class="product-card-body">
            <div class="product-card-name">${p.name}</div>
            <div class="product-card-part">${p.partNumber}</div>
            <div class="product-card-price">$${p.price.toFixed(2)}</div>
            <button class="btn btn-primary btn-sm" onclick="addToCart('${p.productId}', this)">Add to Cart</button>
          </div>
        </div>`).join("");
    } catch (err) {
      document.getElementById("products-loading").style.display = "none";
      const alert = document.getElementById("alert");
      alert.textContent = "Failed to load products: " + err.message;
      alert.style.display = "";
    }
  }

  async function loadCart() {
    try {
      cartItems = await api.getCart();
      renderCart();
    } catch {}
  }

  async function addToCart(productId, btn) {
    const orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Adding…";
    try {
      await api.addToCart(productId, 1);
      cartItems = await api.getCart();
      renderCart();
      const success = document.getElementById("alert-success");
      success.textContent = "Added to cart!";
      success.style.display = "";
      setTimeout(() => success.style.display = "none", 2000);
      btn.textContent = "✓ Added";
      setTimeout(() => { btn.textContent = orig; btn.disabled = false; }, 2000);
    } catch (err) {
      const alert = document.getElementById("alert");
      alert.textContent = err.message;
      alert.style.display = "";
      btn.textContent = orig;
      btn.disabled = false;
    }
  }

  async function removeItem(productId) {
    try {
      await api.removeFromCart(productId);
      cartItems = await api.getCart();
      renderCart();
    } catch (err) {
      alert(err.message);
    }
  }

  async function checkout() {
    const btn = document.getElementById("checkout-btn");
    btn.disabled = true;
    btn.textContent = "Processing…";
    try {
      const order = await api.checkout();
      cartItems = [];
      renderCart();
      const success = document.getElementById("alert-success");
      success.textContent = `Order placed! Total: $${order.total}. Order ID: ${order.orderId.slice(0,8)}…`;
      success.style.display = "";
    } catch (err) {
      const alert = document.getElementById("alert");
      alert.textContent = err.message;
      alert.style.display = "";
    } finally {
      btn.disabled = false;
      btn.textContent = "Checkout";
    }
  }

  loadProducts();
  loadCart();
</script>
</body>
</html>
```

**Step 2: Commit**

```bash
git add website/Products.html
git commit -m "feat: products page with dynamic cart"
```

---

## Task 17: Frontend — AccountInfo.html

**Files:**
- Modify: `website/AccountInfo.html`

**Step 1: Rewrite AccountInfo.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>CloudSev | Account</title>
  <link rel="stylesheet" href="css/app.css" />
</head>
<body>
<nav class="navbar">
  <a class="navbar-brand" href="HomePage.html"><span>Cloud</span>Sev</a>
  <div class="navbar-links">
    <a href="Products.html">Products</a>
    <a href="UsersPastOrders.html">Orders</a>
    <button onclick="logout()">Logout</button>
  </div>
</nav>

<div class="container" style="padding-top:2rem; padding-bottom:3rem; max-width:600px;">
  <div class="page-header">
    <h1>Account Info</h1>
    <a href="HomePage.html" class="btn btn-secondary btn-sm">← Home</a>
  </div>

  <div class="card card-wide" style="max-width:100%;">
    <ul class="info-list" id="info-list">
      <li><strong>Name</strong> <span id="info-name">…</span></li>
      <li><strong>Email</strong> <span id="info-email">…</span></li>
      <li><strong>Status</strong> <span class="badge badge-success">Active</span></li>
    </ul>
    <div style="margin-top:1.5rem; display:flex; gap:0.75rem;">
      <a href="UsersPastOrders.html" class="btn btn-secondary btn-sm">View Past Orders</a>
      <button onclick="logout()" class="btn btn-danger btn-sm">Logout</button>
    </div>
  </div>
</div>

<script src="js/api.js"></script>
<script>
  if (!requireAuth()) throw new Error("redirecting");
  const user = getUser();
  document.getElementById("info-name").textContent = user.name;
  document.getElementById("info-email").textContent = user.email;
</script>
</body>
</html>
```

**Step 2: Commit**

```bash
git add website/AccountInfo.html
git commit -m "feat: account info page from JWT"
```

---

## Task 18: Frontend — UsersPastOrders.html

**Files:**
- Modify: `website/UsersPastOrders.html`

**Step 1: Rewrite UsersPastOrders.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>CloudSev | Orders</title>
  <link rel="stylesheet" href="css/app.css" />
</head>
<body>
<nav class="navbar">
  <a class="navbar-brand" href="HomePage.html"><span>Cloud</span>Sev</a>
  <div class="navbar-links">
    <a href="Products.html">Products</a>
    <a href="AccountInfo.html">Account</a>
    <button onclick="logout()">Logout</button>
  </div>
</nav>

<div class="container" style="padding-top:2rem; padding-bottom:3rem;">
  <div class="page-header">
    <h1>Past Orders</h1>
    <a href="Products.html" class="btn btn-secondary btn-sm">Continue Shopping</a>
  </div>

  <div id="loading" class="loading-state">
    <div class="spinner"></div>
    <p style="margin-top:1rem;">Loading orders…</p>
  </div>

  <div id="empty" class="empty-state" style="display:none">
    <div class="empty-state-icon">📦</div>
    <p>No orders yet. <a href="Products.html" style="color:var(--gold);">Start shopping</a>.</p>
  </div>

  <div id="orders-list" style="display:none"></div>
</div>

<script src="js/api.js"></script>
<script>
  if (!requireAuth()) throw new Error("redirecting");

  function renderOrders(orders) {
    document.getElementById("loading").style.display = "none";
    if (orders.length === 0) {
      document.getElementById("empty").style.display = "";
      return;
    }
    const container = document.getElementById("orders-list");
    container.style.display = "";
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
  }

  api.getOrders()
    .then(renderOrders)
    .catch(err => {
      document.getElementById("loading").innerHTML =
        `<p style="color:var(--danger);">Failed to load orders: ${err.message}</p>`;
    });
</script>
</body>
</html>
```

**Step 2: Commit**

```bash
git add website/UsersPastOrders.html
git commit -m "feat: past orders page with real data"
```

---

## Task 19: Terraform variables and deploy

**Files:**
- Modify: `terraform.tfstate` does not need editing
- You need a `terraform.tfvars` file (do NOT commit this — it contains secrets)

**Step 1: Create terraform.tfvars (do not commit)**

Create `terraform.tfvars` (it should already be gitignored):
```hcl
aws_region     = "us-east-1"
bucket_name    = "your-existing-bucket-name-here"
index_document = "index.html"
error_document = "404.html"
jwt_secret     = "change-this-to-a-long-random-string-32-chars-min"
```

Replace `bucket_name` with the exact name already deployed. Replace `jwt_secret` with a strong random string (e.g. run `python3 -c "import secrets; print(secrets.token_hex(32))"` to generate one).

**Step 2: Add terraform.tfvars to .gitignore**

Check that `.gitignore` (or create it) contains:
```
terraform.tfvars
*.zip
lambda/auth/jwt/
lambda/auth/PyJWT*
lambda/cart/jwt/
lambda/cart/PyJWT*
lambda/orders/jwt/
lambda/orders/PyJWT*
.terraform/
terraform.tfstate
terraform.tfstate.backup
```

**Step 3: Run terraform init (to pick up new providers if needed)**

```bash
terraform init
```

Expected: "Terraform has been successfully initialized"

**Step 4: Run terraform plan**

```bash
terraform plan
```

Review the plan. You should see new resources being created: 4 DynamoDB tables, 5 Lambda functions, 1 API Gateway, IAM role/policy, Lambda permissions, null_resource seeder.

**Step 5: Apply**

```bash
terraform apply
```

Type `yes` when prompted. Wait ~2–3 minutes. Watch for any errors.

**Step 6: Get the API URL and embed it in the frontend**

```bash
terraform output api_url
```

Copy the URL (looks like `https://abc123.execute-api.us-east-1.amazonaws.com`).

Now update `website/js/api.js` — replace the `API_BASE` fallback:
```javascript
const API_BASE = localStorage.getItem("api_url") || "https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com";
```

Replace `YOUR-API-ID` with the actual value.

**Step 7: Re-apply to push updated frontend files**

```bash
terraform apply
```

This re-uploads the updated `api.js` to S3.

**Step 8: Verify the deployment**

```bash
terraform output website_url
```

Open that URL in a browser. You should see the Login page.

Manual smoke test:
1. Open the site URL
2. Click "Sign up" and create an account → should redirect to HomePage
3. Click "Browse Products" → products should load from DynamoDB
4. Click "Add to Cart" on a product → cart panel should appear with the item
5. Click "Checkout" → should create an order and clear the cart
6. Navigate to "Past Orders" → your order should appear
7. Navigate to "Account" → your name and email should show

**Step 9: Commit**

```bash
git add website/js/api.js
git commit -m "feat: wire api_url into frontend after deploy"
```

---

## Summary of all new files

| File | Purpose |
|---|---|
| `dynamodb.tf` | 4 DynamoDB tables |
| `iam.tf` | Lambda IAM role + DynamoDB policy |
| `lambda.tf` | 5 Lambda functions + zip packaging |
| `api_gateway.tf` | HTTP API + routes + Lambda permissions + seeder |
| `lambda/auth/handler.py` | Signup + login |
| `lambda/products/handler.py` | List products |
| `lambda/cart/handler.py` | Cart CRUD |
| `lambda/orders/handler.py` | Checkout + order history |
| `lambda/seeder/handler.py` | Seed 3 products on deploy |
| `tests/` | pytest + moto unit tests |
| `website/css/app.css` | Full design system |
| `website/js/api.js` | Shared fetch helper + auth guard |
| `website/Login.html` | Real auth with sign up / sign in |
| `website/HomePage.html` | Dynamic greeting + cart count |
| `website/Products.html` | Dynamic products + working cart + checkout |
| `website/AccountInfo.html` | User info from JWT |
| `website/UsersPastOrders.html` | Real order history from DynamoDB |
