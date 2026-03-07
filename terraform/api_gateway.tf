# HTTP API (API Gateway v2) — simpler and cheaper than v1 for webhook use
resource "aws_apigatewayv2_api" "telegram_webhook" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"
}

# Route: POST /webhook — Telegram sends all updates here
resource "aws_apigatewayv2_route" "webhook" {
  api_id    = aws_apigatewayv2_api.telegram_webhook.id
  route_key = "POST /webhook"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Integration — connects the route to the Lambda function
resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.telegram_webhook.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.assistant.invoke_arn
  payload_format_version = "2.0"
}

# Default stage — auto-deploys on changes
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.telegram_webhook.id
  name        = "$default"
  auto_deploy = true
}

# Output the webhook URL — you'll need this to register with Telegram
output "webhook_url" {
  value       = "${aws_apigatewayv2_stage.default.invoke_url}/webhook"
  description = "Register this URL as your Telegram bot webhook"
}
