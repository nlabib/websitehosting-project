# ── Install Python deps for lambdas that need PyJWT ──────────────

resource "null_resource" "install_auth_deps" {
  triggers = {
    req_hash = filemd5("${path.module}/lambda/auth/requirements.txt")
  }
  provisioner "local-exec" {
    command = "pip3 install -r ${path.module}/lambda/auth/requirements.txt -t ${path.module}/lambda/auth/ --quiet --upgrade"
  }
}

resource "null_resource" "install_cart_deps" {
  triggers = {
    req_hash = filemd5("${path.module}/lambda/cart/requirements.txt")
  }
  provisioner "local-exec" {
    command = "pip3 install -r ${path.module}/lambda/cart/requirements.txt -t ${path.module}/lambda/cart/ --quiet --upgrade"
  }
}

resource "null_resource" "install_orders_deps" {
  triggers = {
    req_hash = filemd5("${path.module}/lambda/orders/requirements.txt")
  }
  provisioner "local-exec" {
    command = "pip3 install -r ${path.module}/lambda/orders/requirements.txt -t ${path.module}/lambda/orders/ --quiet --upgrade"
  }
}

# ── Zip archives ──────────────────────────────────────────────────

data "archive_file" "auth_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/auth"
  output_path = "${path.module}/lambda/auth.zip"
  excludes    = ["requirements.txt", "__pycache__"]
  depends_on  = [null_resource.install_auth_deps]
}

data "archive_file" "products_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/products"
  output_path = "${path.module}/lambda/products.zip"
  excludes    = ["__pycache__"]
}

data "archive_file" "cart_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/cart"
  output_path = "${path.module}/lambda/cart.zip"
  excludes    = ["requirements.txt", "__pycache__"]
  depends_on  = [null_resource.install_cart_deps]
}

data "archive_file" "orders_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/orders"
  output_path = "${path.module}/lambda/orders.zip"
  excludes    = ["requirements.txt", "__pycache__"]
  depends_on  = [null_resource.install_orders_deps]
}

data "archive_file" "seeder_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/seeder"
  output_path = "${path.module}/lambda/seeder.zip"
  excludes    = ["__pycache__"]
}

# ── Shared environment variables for all lambdas ─────────────────

locals {
  lambda_env = {
    USERS_TABLE    = aws_dynamodb_table.users.name
    PRODUCTS_TABLE = aws_dynamodb_table.products.name
    CART_TABLE     = aws_dynamodb_table.cart.name
    ORDERS_TABLE   = aws_dynamodb_table.orders.name
    JWT_SECRET     = var.jwt_secret
  }
}

# ── Lambda functions ──────────────────────────────────────────────

resource "aws_lambda_function" "auth" {
  filename         = data.archive_file.auth_zip.output_path
  function_name    = "cloudsev-auth"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.auth_zip.output_base64sha256
  timeout          = 15
  environment { variables = local.lambda_env }
  tags = { Project = "cloudsev", ManagedBy = "Terraform" }
}

resource "aws_lambda_function" "products" {
  filename         = data.archive_file.products_zip.output_path
  function_name    = "cloudsev-products"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.products_zip.output_base64sha256
  timeout          = 10
  environment { variables = local.lambda_env }
  tags = { Project = "cloudsev", ManagedBy = "Terraform" }
}

resource "aws_lambda_function" "cart" {
  filename         = data.archive_file.cart_zip.output_path
  function_name    = "cloudsev-cart"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.cart_zip.output_base64sha256
  timeout          = 10
  environment { variables = local.lambda_env }
  tags = { Project = "cloudsev", ManagedBy = "Terraform" }
}

resource "aws_lambda_function" "orders" {
  filename         = data.archive_file.orders_zip.output_path
  function_name    = "cloudsev-orders"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.orders_zip.output_base64sha256
  timeout          = 15
  environment { variables = local.lambda_env }
  tags = { Project = "cloudsev", ManagedBy = "Terraform" }
}

resource "aws_lambda_function" "seeder" {
  filename         = data.archive_file.seeder_zip.output_path
  function_name    = "cloudsev-seeder"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.seeder_zip.output_base64sha256
  timeout          = 30
  environment {
    variables = {
      PRODUCTS_TABLE = aws_dynamodb_table.products.name
    }
  }
  tags = { Project = "cloudsev", ManagedBy = "Terraform" }
}

resource "null_resource" "install_custom_print_deps" {
  triggers = {
    req_hash = filemd5("${path.module}/lambda/custom-print/requirements.txt")
  }
  provisioner "local-exec" {
    command = "pip3 install -r ${path.module}/lambda/custom-print/requirements.txt -t ${path.module}/lambda/custom-print/ --quiet --upgrade"
  }
}

data "archive_file" "custom_print_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/custom-print"
  output_path = "${path.module}/lambda/custom-print.zip"
  excludes    = ["requirements.txt", "__pycache__"]
  depends_on  = [null_resource.install_custom_print_deps]
}

resource "aws_lambda_function" "custom_print" {
  filename         = data.archive_file.custom_print_zip.output_path
  function_name    = "cloudsev-custom-print"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.custom_print_zip.output_base64sha256
  timeout          = 15
  environment {
    variables = merge(local.lambda_env, {
      DESIGNS_BUCKET = aws_s3_bucket.designs.bucket
    })
  }
  tags = { Project = "cloudsev", ManagedBy = "Terraform" }
}
