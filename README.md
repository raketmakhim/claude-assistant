# Claude Personal Assistant

A personal AI assistant powered by Claude, accessible via Telegram. Remembers important information across sessions and creates Google Calendar events on your behalf.

---

## Features

- **Chat** — natural conversation via Telegram on any device
- **Persistent memory** — remembers facts, dates, and preferences across sessions (stored in DynamoDB)
- **Google Calendar** — creates and deletes calendar events from natural language
- **Error resilience** — tool failures are caught and reported; the bot always replies

---

## Architecture

```
[Telegram App]
      │
      ▼
[AWS API Gateway]  ←  validates secret token
      │
      ▼
[AWS Lambda]
      ├── [Claude API]         — understands message, calls tools
      ├── [DynamoDB]           — reads/writes persistent memories
      └── [Google Calendar]   — creates/deletes events
      │
      ▼
[Telegram API]  →  sends reply to user
```

---

## AWS Services

| Service | Role |
|---|---|
| **Lambda** | Core backend — handles messages, calls Claude, executes tools |
| **API Gateway** | Receives Telegram webhook (HTTP POST) |
| **DynamoDB** | Persistent memory store |
| **Secrets Manager** | Stores all API keys securely |
| **IAM** | Least-privilege roles between services |
| **CloudWatch** | Lambda logs (30-day retention) |

---

## Project Structure

```
├── lambda/
│   ├── handler.py          # Lambda entry point
│   ├── claude_client.py    # Anthropic client + tool definitions
│   ├── google_calendar.py  # Google Calendar API (create/delete events)
│   ├── memory.py           # DynamoDB read/write/delete
│   ├── secrets.py          # AWS Secrets Manager (cached)
│   └── telegram.py         # Telegram Bot API (send messages)
│
├── terraform/
│   ├── main.tf             # Provider config
│   ├── variables.tf        # Region, project name, runtime
│   ├── lambda.tf           # Lambda function + CloudWatch log group
│   ├── api_gateway.tf      # HTTP API + webhook route
│   ├── dynamodb.tf         # Memories table
│   ├── iam.tf              # Execution role + policies
│   └── secrets.tf          # Secrets Manager secret
│
├── .gitignore
└── README.md
```

---

## Prerequisites

- AWS account with CLI configured (`aws configure`)
- Terraform >= 1.6
- Python 3.12
- Telegram bot token (from [@BotFather](https://t.me/BotFather))
- Claude API key (from [console.anthropic.com](https://console.anthropic.com))
- Google Cloud service account with Calendar API enabled

---

## Setup

### 1. Deploy infrastructure

```bash
cd terraform
terraform init
terraform apply
```

Note the `webhook_url` output.

### 2. Add secrets

In AWS Secrets Manager, set the secret value to:

```json
{
  "CLAUDE_API_KEY": "...",
  "TELEGRAM_BOT_TOKEN": "...",
  "TELEGRAM_SECRET_TOKEN": "any-random-string",
  "GOOGLE_SERVICE_ACCOUNT": { ... },
  "GOOGLE_CALENDAR_ID": "your@gmail.com"
}
```

`GOOGLE_SERVICE_ACCOUNT` is the full JSON key file downloaded from Google Cloud Console.
`GOOGLE_CALENDAR_ID` is found in Google Calendar → Settings → your calendar → Integrate calendar.

### 3. Install Lambda dependencies

```bash
pip install anthropic google-api-python-client google-auth-httplib2 google-auth -t lambda/ \
  --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.12
```

### 4. Register the Telegram webhook

```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=<WEBHOOK_URL>" \
  -d "secret_token=<TELEGRAM_SECRET_TOKEN>"
```

### 5. Deploy Lambda code

```bash
cd terraform
terraform apply
```

---

## Claude Tools

| Tool | Trigger | Effect |
|---|---|---|
| `create_calendar_event` | Appointment or event mentioned | Creates Google Calendar event + saves to memory |
| `save_memory` | Personal info or preference shared | Writes to DynamoDB |
| `delete_memory` | "Forget / cancel / delete that" | Removes from DynamoDB + deletes linked calendar event |

---

## Memory Data Model (DynamoDB)

| Field | Type | Description |
|---|---|---|
| `id` | String (PK) | UUID |
| `type` | String | `fact` / `event` / `reminder` |
| `label` | String | Human-readable description |
| `date` | String | ISO date if applicable |
| `created_at` | String | ISO timestamp |
| `raw` | String | Original user message |
| `calendar_event_id` | String | Google Calendar event ID (if linked) |
