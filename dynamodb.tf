resource "aws_dynamodb_table" "users" {
  name         = "cloudsev-users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"

  attribute {
    name = "userId"
    type = "S"
  }

  tags = { Project = "cloudsev", ManagedBy = "Terraform" }
}

resource "aws_dynamodb_table" "products" {
  name         = "cloudsev-products"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "productId"

  attribute {
    name = "productId"
    type = "S"
  }

  tags = { Project = "cloudsev", ManagedBy = "Terraform" }
}

resource "aws_dynamodb_table" "cart" {
  name         = "cloudsev-cart"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"
  range_key    = "productId"

  attribute {
    name = "userId"
    type = "S"
  }
  attribute {
    name = "productId"
    type = "S"
  }

  tags = { Project = "cloudsev", ManagedBy = "Terraform" }
}

resource "aws_dynamodb_table" "orders" {
  name         = "cloudsev-orders"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"
  range_key    = "orderId"

  attribute {
    name = "userId"
    type = "S"
  }
  attribute {
    name = "orderId"
    type = "S"
  }

  tags = { Project = "cloudsev", ManagedBy = "Terraform" }
}
