import json
import importlib.util
import os
import boto3
from decimal import Decimal

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_products():
    path = os.path.join(PROJECT_ROOT, "lambda/products/handler.py")
    spec = importlib.util.spec_from_file_location("_products_h", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_list_products_empty(aws_tables):
    products = _load_products()
    resp = products.lambda_handler({}, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == []


def test_list_products_returns_items(aws_tables):
    products = _load_products()
    table = boto3.resource("dynamodb", region_name="us-east-1").Table("cloudsev-products")
    table.put_item(Item={"productId": "p1", "name": "Hat", "price": Decimal("9.99"), "partNumber": "HAT-1"})
    resp = products.lambda_handler({}, None)
    body = json.loads(resp["body"])
    assert len(body) == 1
    assert body[0]["name"] == "Hat"
    assert body[0]["price"] == 9.99
