import json
import os
import uuid
import hashlib
import hmac
import boto3
from boto3.dynamodb.conditions import Attr
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
    resp = table.scan(FilterExpression=Attr("email").eq(email))
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
    resp = table.scan(FilterExpression=Attr("email").eq(email))
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
