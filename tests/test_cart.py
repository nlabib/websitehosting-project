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


def _signup_token(auth, email="t@t.com"):
    resp = auth.lambda_handler(
        {"routeKey": "POST /auth/signup", "body": json.dumps({"name": "T", "email": email, "password": "pw"}), "headers": {}},
        None,
    )
    return json.loads(resp["body"])["token"]


def _auth_event(route, token, body=None, path_params=None):
    return {
        "routeKey": route,
        "headers": {"authorization": f"Bearer {token}"},
        "body": json.dumps(body) if body else None,
        "pathParameters": path_params or {},
    }


def test_get_empty_cart(aws_tables):
    auth = _load("lambda/auth/handler.py", "_auth_cart1")
    cart = _load("lambda/cart/handler.py", "_cart_h1")
    token = _signup_token(auth)
    resp = cart.lambda_handler(_auth_event("GET /cart", token), None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == []


def test_add_and_get_cart(aws_tables):
    auth = _load("lambda/auth/handler.py", "_auth_cart2")
    cart = _load("lambda/cart/handler.py", "_cart_h2")
    table = boto3.resource("dynamodb", region_name="us-east-1").Table("cloudsev-products")
    table.put_item(Item={"productId": "hat-001", "name": "Hat", "price": Decimal("9.99"), "partNumber": "HAT-1", "imageUrl": "hat.png"})
    token = _signup_token(auth)
    cart.lambda_handler(_auth_event("POST /cart", token, {"productId": "hat-001", "quantity": 2}), None)
    resp = cart.lambda_handler(_auth_event("GET /cart", token), None)
    items = json.loads(resp["body"])
    assert len(items) == 1
    assert items[0]["productId"] == "hat-001"
    assert items[0]["quantity"] == 2


def test_remove_from_cart(aws_tables):
    auth = _load("lambda/auth/handler.py", "_auth_cart3")
    cart = _load("lambda/cart/handler.py", "_cart_h3")
    table = boto3.resource("dynamodb", region_name="us-east-1").Table("cloudsev-products")
    table.put_item(Item={"productId": "hat-001", "name": "Hat", "price": Decimal("9.99"), "partNumber": "HAT-1", "imageUrl": "hat.png"})
    token = _signup_token(auth)
    cart.lambda_handler(_auth_event("POST /cart", token, {"productId": "hat-001"}), None)
    cart.lambda_handler(_auth_event("DELETE /cart/{productId}", token, path_params={"productId": "hat-001"}), None)
    resp = cart.lambda_handler(_auth_event("GET /cart", token), None)
    assert json.loads(resp["body"]) == []


def test_unauthorized_cart(aws_tables):
    cart = _load("lambda/cart/handler.py", "_cart_h4")
    resp = cart.lambda_handler({"routeKey": "GET /cart", "headers": {}, "body": None, "pathParameters": {}}, None)
    assert resp["statusCode"] == 401
