import os
import boto3
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")

PRODUCTS = [
    {
        "productId": "hat-001",
        "partNumber": "HAT-123",
        "name": "CloudSev Cap",
        "price": Decimal("9.99"),
        "imageUrl": "hat.png",
    },
    {
        "productId": "shirt-001",
        "partNumber": "SHIRT-123",
        "name": "CloudSev T-Shirt",
        "price": Decimal("19.99"),
        "imageUrl": "shirt.png",
    },
    {
        "productId": "shoes-001",
        "partNumber": "SHOES-123",
        "name": "CloudSev Sneakers",
        "price": Decimal("49.99"),
        "imageUrl": "shoes.png",
    },
]


def lambda_handler(event, context):
    table = dynamodb.Table(os.environ["PRODUCTS_TABLE"])
    for product in PRODUCTS:
        table.put_item(Item=product)
    print(f"Seeded {len(PRODUCTS)} products into {os.environ['PRODUCTS_TABLE']}")
    return {"statusCode": 200, "body": "seeded"}
