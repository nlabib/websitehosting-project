import json
import importlib.util
import os
import boto3
import jwt as _jwt
from boto3.dynamodb.conditions import Key

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


def _event(route, token, body=None, path_params=None):
    return {
        "routeKey": route,
        "headers": {"authorization": f"Bearer {token}"},
        "body": json.dumps(body) if body else None,
        "pathParameters": path_params or {},
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
    # Verify the record was actually written to DynamoDB
    user_id = _jwt.decode(token, "test-secret-key", algorithms=["HS256"])["sub"]
    table = boto3.resource("dynamodb", region_name="us-east-1").Table("cloudsev-orders")
    result = table.query(KeyConditionExpression=Key("userId").eq(user_id))
    assert len(result["Items"]) == 1
    item = result["Items"][0]
    assert item["type"] == "custom-print"
    assert item["designKey"] == "uploads/abc/xyz.png"
    assert item["notes"] == "blue ink on front"


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
