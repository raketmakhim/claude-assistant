# Single secret holding all API keys as a JSON object
resource "aws_secretsmanager_secret" "api_keys" {
  name                    = "${var.project_name}/api-keys"
  description             = "API keys for Claude, Telegram, and Google Calendar"
  recovery_window_in_days = 0 # Allow immediate deletion (useful during dev)
}

# Placeholder values — update these manually in AWS Console after deploy
# Never put real keys in Terraform files
# resource "aws_secretsmanager_secret_version" "api_keys" {
#   secret_id = aws_secretsmanager_secret.api_keys.id

#   secret_string = jsonencode({
#     CLAUDE_API_KEY          = "REPLACE_ME"
#     TELEGRAM_BOT_TOKEN      = "REPLACE_ME"
#     TELEGRAM_SECRET_TOKEN   = "REPLACE_ME"
#     GOOGLE_CLIENT_ID        = "REPLACE_ME"
#     GOOGLE_CLIENT_SECRET    = "REPLACE_ME"
#     GOOGLE_REFRESH_TOKEN    = "REPLACE_ME"
#   })
# }
