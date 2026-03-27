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
      SECRETS_PATH      = aws_ssm_parameter.api_keys.name
      GOOGLE_SA_PATH    = aws_ssm_parameter.google_service_account.name
      DYNAMODB_TABLE    = aws_dynamodb_table.memories.name
      LUNCH_IDEAS_TABLE = aws_dynamodb_table.lunch_ideas.name
      AWS_REGION_NAME   = var.aws_region
    }
  }

  tags = {
    Project = var.project_name
  }
}

# Scheduler Lambda — daily lunch idea sender (no Claude, no API Gateway)
resource "aws_lambda_function" "scheduler" {
  function_name    = "${var.project_name}-scheduler"
  role             = aws_iam_role.lambda_exec.arn
  runtime          = var.lambda_runtime
  handler          = "scheduler.lambda_handler"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  timeout     = 10
  memory_size = 128

  environment {
    variables = {
      SECRETS_PATH      = aws_ssm_parameter.api_keys.name
      GOOGLE_SA_PATH    = aws_ssm_parameter.google_service_account.name
      DYNAMODB_TABLE    = aws_dynamodb_table.memories.name
      LUNCH_IDEAS_TABLE = aws_dynamodb_table.lunch_ideas.name
      AWS_REGION_NAME   = var.aws_region
    }
  }

  tags = {
    Project = var.project_name
  }
}

resource "aws_cloudwatch_log_group" "scheduler_logs" {
  name              = "/aws/lambda/${var.project_name}-scheduler"
  retention_in_days = 30
}

# EventBridge rule — fires daily at 08:00 UTC (9am UK winter / 10am UK summer)
resource "aws_cloudwatch_event_rule" "daily_lunch" {
  name                = "${var.project_name}-daily-lunch"
  description         = "Sends a random daily lunch idea via Telegram"
  schedule_expression = "cron(0 8 * * ? *)"
}

resource "aws_cloudwatch_event_target" "daily_lunch_target" {
  rule      = aws_cloudwatch_event_rule.daily_lunch.name
  target_id = "LunchScheduler"
  arn       = aws_lambda_function.scheduler.arn
}

resource "aws_lambda_permission" "eventbridge_scheduler" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scheduler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_lunch.arn
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
