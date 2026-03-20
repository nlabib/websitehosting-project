# ── HTTP API with CORS ────────────────────────────────────────────

resource "aws_apigatewayv2_api" "cloudsev" {
  name          = "cloudsev-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "DELETE", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization"]
    max_age       = 300
  }

  tags = { Project = "cloudsev", ManagedBy = "Terraform" }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.cloudsev.id
  name        = "$default"
  auto_deploy = true
}

# ── Lambda integrations ───────────────────────────────────────────

resource "aws_apigatewayv2_integration" "auth" {
  api_id                 = aws_apigatewayv2_api.cloudsev.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.auth.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "products" {
  api_id                 = aws_apigatewayv2_api.cloudsev.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.products.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "cart" {
  api_id                 = aws_apigatewayv2_api.cloudsev.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.cart.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "orders" {
  api_id                 = aws_apigatewayv2_api.cloudsev.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.orders.invoke_arn
  payload_format_version = "2.0"
}

# ── Routes ────────────────────────────────────────────────────────

resource "aws_apigatewayv2_route" "signup" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "POST /auth/signup"
  target    = "integrations/${aws_apigatewayv2_integration.auth.id}"
}

resource "aws_apigatewayv2_route" "login" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "POST /auth/login"
  target    = "integrations/${aws_apigatewayv2_integration.auth.id}"
}

resource "aws_apigatewayv2_route" "products_get" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "GET /products"
  target    = "integrations/${aws_apigatewayv2_integration.products.id}"
}

resource "aws_apigatewayv2_route" "cart_get" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "GET /cart"
  target    = "integrations/${aws_apigatewayv2_integration.cart.id}"
}

resource "aws_apigatewayv2_route" "cart_post" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "POST /cart"
  target    = "integrations/${aws_apigatewayv2_integration.cart.id}"
}

resource "aws_apigatewayv2_route" "cart_delete" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "DELETE /cart/{productId}"
  target    = "integrations/${aws_apigatewayv2_integration.cart.id}"
}

resource "aws_apigatewayv2_route" "orders_post" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "POST /orders"
  target    = "integrations/${aws_apigatewayv2_integration.orders.id}"
}

resource "aws_apigatewayv2_route" "orders_get" {
  api_id    = aws_apigatewayv2_api.cloudsev.id
  route_key = "GET /orders"
  target    = "integrations/${aws_apigatewayv2_integration.orders.id}"
}

# ── Lambda invoke permissions ─────────────────────────────────────

resource "aws_lambda_permission" "auth_apigw" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auth.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.cloudsev.execution_arn}/*/*"
}

resource "aws_lambda_permission" "products_apigw" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.products.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.cloudsev.execution_arn}/*/*"
}

resource "aws_lambda_permission" "cart_apigw" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cart.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.cloudsev.execution_arn}/*/*"
}

resource "aws_lambda_permission" "orders_apigw" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.orders.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.cloudsev.execution_arn}/*/*"
}

# ── Product seeder (runs once after deploy) ───────────────────────

resource "null_resource" "seed_products" {
  triggers = {
    seeder_hash   = aws_lambda_function.seeder.source_code_hash
    table_created = aws_dynamodb_table.products.id
  }

  provisioner "local-exec" {
    command = "aws lambda invoke --function-name ${aws_lambda_function.seeder.function_name} --region ${var.aws_region} /dev/null"
  }

  depends_on = [
    aws_lambda_function.seeder,
    aws_dynamodb_table.products,
    aws_iam_role_policy.dynamodb_access,
  ]
}
