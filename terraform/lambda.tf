# Zip the lambda source code for deployment
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda"
  output_path = "${path.module}/../lambda.zip"
}

resource "aws_lambda_function" "assistant" {
  function_name    = "${var.project_name}-handler"
  role             = aws_iam_role.lambda_exec.arn
  runtime          = var.lambda_runtime
  handler          = "handler.lambda_handler"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  timeout                        = 30 # seconds — Claude API calls can take a moment
  memory_size                    = 256
  
  environment {
    variables = {
      SECRETS_ARN    = aws_secretsmanager_secret.api_keys.arn
      DYNAMODB_TABLE = aws_dynamodb_table.memories.name
      AWS_REGION_NAME = var.aws_region
    }
  }

  tags = {
    Project = var.project_name
  }
}

# CloudWatch log group with 30-day retention
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.project_name}-handler"
  retention_in_days = 30
}

# Allow API Gateway to invoke this Lambda
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.assistant.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.telegram_webhook.execution_arn}/*/*"
}
