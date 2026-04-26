import json
import importlib.util
import os
import boto3
from decimal import Decimal

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(rel_path, mod_name):
    path = os.path.join(PROJECT_ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _signup_token(auth, email="u@u.com"):
    resp = auth.lambda_handler(
        {"routeKey": "POST /auth/signup", "body": json.dumps({"name": "U", "email": email, "password": "pw"}), "headers": {}},
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


def test_checkout_empty_cart(aws_tables):
    auth = _load("lambda/auth/handler.py", "_auth_ord1")
    orders = _load("lambda/orders/handler.py", "_orders_h1")
    token = _signup_token(auth)
    resp = orders.lambda_handler(_event("POST /orders", token), None)
    assert resp["statusCode"] == 400


def test_checkout_creates_order_and_clears_cart(aws_tables):
    auth = _load("lambda/auth/handler.py", "_auth_ord2")
    cart = _load("lambda/cart/handler.py", "_cart_ord2")
    orders = _load("lambda/orders/handler.py", "_orders_h2")
    table = boto3.resource("dynamodb", region_name="us-east-1").Table("cloudsev-products")
    table.put_item(Item={"productId": "shirt-001", "name": "Shirt", "price": Decimal("19.99"), "partNumber": "SHIRT-1", "imageUrl": "shirt.png"})
    token = _signup_token(auth)
    cart.lambda_handler({"routeKey": "POST /cart", "headers": {"authorization": f"Bearer {token}"}, "body": json.dumps({"productId": "shirt-001", "quantity": 1}), "pathParameters": {}}, None)
    resp = orders.lambda_handler(_event("POST /orders", token), None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "orderId" in body
    assert body["total"] == "19.99"
    # Cart should now be empty
    cart_resp = cart.lambda_handler({"routeKey": "GET /cart", "headers": {"authorization": f"Bearer {token}"}, "body": None, "pathParameters": {}}, None)
    assert json.loads(cart_resp["body"]) == []


def test_list_orders(aws_tables):
    auth = _load("lambda/auth/handler.py", "_auth_ord3")
    cart = _load("lambda/cart/handler.py", "_cart_ord3")
    orders = _load("lambda/orders/handler.py", "_orders_h3")
    table = boto3.resource("dynamodb", region_name="us-east-1").Table("cloudsev-products")
    table.put_item(Item={"productId": "shoes-001", "name": "Shoes", "price": Decimal("49.99"), "partNumber": "SHOES-1", "imageUrl": "shoes.png"})
    token = _signup_token(auth, "v@v.com")
    cart.lambda_handler({"routeKey": "POST /cart", "headers": {"authorization": f"Bearer {token}"}, "body": json.dumps({"productId": "shoes-001"}), "pathParameters": {}}, None)
    orders.lambda_handler(_event("POST /orders", token), None)
    resp = orders.lambda_handler(_event("GET /orders", token), None)
    order_list = json.loads(resp["body"])
    assert len(order_list) == 1
    assert order_list[0]["total"] == "49.99"


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
