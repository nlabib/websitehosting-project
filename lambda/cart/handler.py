import json
import os
import boto3
from boto3.dynamodb.conditions import Key
import jwt

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


def _get_cart(user_id):
    table = dynamodb.Table(os.environ["CART_TABLE"])
    products_table = dynamodb.Table(os.environ["PRODUCTS_TABLE"])
    resp = table.query(
        KeyConditionExpression=Key("userId").eq(user_id)
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
