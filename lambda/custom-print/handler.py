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
