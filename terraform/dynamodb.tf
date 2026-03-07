resource "aws_dynamodb_table" "memories" {
  name         = "${var.project_name}-memories"
  billing_mode = "PAY_PER_REQUEST" # No provisioned capacity — cheapest for personal use
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  # TTL — optionally auto-expire old reminders after their date passes
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Project = var.project_name
  }
}
