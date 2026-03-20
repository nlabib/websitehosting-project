import os
import pytest
import boto3
from moto import mock_aws

os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["USERS_TABLE"] = "cloudsev-users"
os.environ["PRODUCTS_TABLE"] = "cloudsev-products"
os.environ["CART_TABLE"] = "cloudsev-cart"
os.environ["ORDERS_TABLE"] = "cloudsev-orders"


@pytest.fixture
def aws_tables():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        # users
        client.create_table(
            TableName="cloudsev-users",
            KeySchema=[{"AttributeName": "userId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "userId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        # products
        client.create_table(
            TableName="cloudsev-products",
            KeySchema=[{"AttributeName": "productId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "productId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        # cart
        client.create_table(
            TableName="cloudsev-cart",
            KeySchema=[
                {"AttributeName": "userId", "KeyType": "HASH"},
                {"AttributeName": "productId", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "userId", "AttributeType": "S"},
                {"AttributeName": "productId", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        # orders
        client.create_table(
            TableName="cloudsev-orders",
            KeySchema=[
                {"AttributeName": "userId", "KeyType": "HASH"},
                {"AttributeName": "orderId", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "userId", "AttributeType": "S"},
                {"AttributeName": "orderId", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield
