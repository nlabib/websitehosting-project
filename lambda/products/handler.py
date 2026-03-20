import json
import os
import boto3

dynamodb = boto3.resource("dynamodb")


def _ok(body):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    table = dynamodb.Table(os.environ["PRODUCTS_TABLE"])
    resp = table.scan()
    products = sorted(resp.get("Items", []), key=lambda p: p.get("partNumber", ""))
    # Convert Decimal to float for JSON serialization
    for p in products:
        if "price" in p:
            p["price"] = float(p["price"])
    return _ok(products)
