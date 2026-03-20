import json
import os
import uuid
import boto3
from boto3.dynamodb.conditions import Key
import jwt
from datetime import datetime, timezone
from decimal import Decimal

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


def _checkout(user_id):
    cart_table = dynamodb.Table(os.environ["CART_TABLE"])
    products_table = dynamodb.Table(os.environ["PRODUCTS_TABLE"])
    orders_table = dynamodb.Table(os.environ["ORDERS_TABLE"])

    cart_resp = cart_table.query(
        KeyConditionExpression=Key("userId").eq(user_id)
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

    # Clear cart
    with cart_table.batch_writer() as batch:
        for item in cart_items:
            batch.delete_item(Key={"userId": user_id, "productId": item["productId"]})

    return _ok({"orderId": order_id, "total": str(total), "date": date_str})


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
        orders.append({
            "orderId": o["orderId"],
            "total": str(o.get("total", "0")),
            "date": o.get("date", ""),
            "delivered": bool(o.get("delivered", False)),
            "items": items,
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
