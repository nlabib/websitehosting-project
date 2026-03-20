import json
import importlib.util
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_auth():
    path = os.path.join(PROJECT_ROOT, "lambda/auth/handler.py")
    spec = importlib.util.spec_from_file_location("_auth_h", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _event(route, body):
    return {"routeKey": route, "body": json.dumps(body), "headers": {}}


def test_signup_success(aws_tables):
    auth = _load_auth()
    event = _event("POST /auth/signup", {"name": "Alice", "email": "alice@test.com", "password": "pass123"})
    resp = auth.lambda_handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "token" in body
    assert body["email"] == "alice@test.com"


def test_signup_missing_fields(aws_tables):
    auth = _load_auth()
    event = _event("POST /auth/signup", {"email": "x@test.com"})
    resp = auth.lambda_handler(event, None)
    assert resp["statusCode"] == 400


def test_signup_duplicate_email(aws_tables):
    auth = _load_auth()
    event = _event("POST /auth/signup", {"name": "Alice", "email": "alice@test.com", "password": "pass123"})
    auth.lambda_handler(event, None)
    resp = auth.lambda_handler(event, None)
    assert resp["statusCode"] == 409


def test_login_success(aws_tables):
    auth = _load_auth()
    auth.lambda_handler(_event("POST /auth/signup", {"name": "Bob", "email": "bob@test.com", "password": "secret"}), None)
    resp = auth.lambda_handler(_event("POST /auth/login", {"email": "bob@test.com", "password": "secret"}), None)
    assert resp["statusCode"] == 200
    assert "token" in json.loads(resp["body"])


def test_login_wrong_password(aws_tables):
    auth = _load_auth()
    auth.lambda_handler(_event("POST /auth/signup", {"name": "Bob", "email": "bob@test.com", "password": "secret"}), None)
    resp = auth.lambda_handler(_event("POST /auth/login", {"email": "bob@test.com", "password": "wrong"}), None)
    assert resp["statusCode"] == 401


def test_login_unknown_email(aws_tables):
    auth = _load_auth()
    resp = auth.lambda_handler(_event("POST /auth/login", {"email": "ghost@test.com", "password": "x"}), None)
    assert resp["statusCode"] == 401
