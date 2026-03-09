# Single SecureString parameter holding all API keys as a JSON object
# Standard tier — free (unlike Secrets Manager at $0.40/month)
resource "aws_ssm_parameter" "api_keys" {
  name        = "/${var.project_name}/api-keys"
  type        = "SecureString"
  description = "API keys for Claude, Telegram, and Google Calendar"

  # Placeholder — update manually in AWS Console after deploy
  # Never put real keys in Terraform files
  value = jsonencode({
    CLAUDE_API_KEY        = "REPLACE_ME"
    TELEGRAM_BOT_TOKEN    = "REPLACE_ME"
    TELEGRAM_SECRET_TOKEN = "REPLACE_ME"
    GOOGLE_CALENDAR_ID    = "REPLACE_ME"
  })

  lifecycle {
    ignore_changes = [value] # prevent Terraform overwriting manually set values
  }
}

# Google service account JSON stored separately to avoid nesting issues
resource "aws_ssm_parameter" "google_service_account" {
  name        = "/${var.project_name}/google-service-account"
  type        = "SecureString"
  description = "Google service account JSON key for Calendar API"
  value       = "REPLACE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}
