variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "eu-west-2" # London
}

variable "project_name" {
  description = "Project name used to prefix all resources"
  type        = string
  default     = "claude-assistant"
}

variable "lambda_runtime" {
  description = "Python runtime for Lambda"
  type        = string
  default     = "python3.12"
}
