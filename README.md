# Claude Personal Assistant

A personal AI assistant powered by Claude, accessible via Telegram. Remembers facts across sessions, creates Google Calendar events, and schedules spaced-repetition study reviews.

---

## Features

- **Chat** — natural conversation via Telegram on any device
- **Persistent memory** — remembers facts and preferences across sessions (stored in DynamoDB)
- **Google Calendar** — creates and deletes calendar events from natural language, no details required
- **Spaced repetition** — log a study session and automatically schedule Day 7 and Day 30 review reminders
- **Parallel tool execution** — multiple tool calls (e.g. create several events at once) run concurrently
- **Prompt caching** — reduces Claude API costs on repeated requests
- **Auto-expiry** — calendar-linked memories expire from DynamoDB one day after the event date
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
      ├── [Claude API]         — understands message, decides which tools to call
      ├── [DynamoDB]           — reads/writes persistent memories (with TTL)
      └── [Google Calendar]   — creates/deletes events via service account
      │
      ▼
[Telegram API]  →  sends reply to user
```

---

## AWS Services

| Service | Role |
|---|---|
| **Lambda** | Core backend — handles messages, runs Claude agentic loop, executes tools |
| **API Gateway** | Receives Telegram webhook (HTTP POST) |
| **DynamoDB** | Persistent memory store with TTL auto-expiry |
| **Secrets Manager** | Stores all API keys securely |
| **IAM** | Least-privilege roles between services |
| **CloudWatch** | Lambda logs (30-day retention) |

---

## Project Structure

```
├── lambda/
│   ├── handler.py          # Lambda entry point + agentic loop + tool dispatch
│   ├── claude_client.py    # Anthropic client + tool definitions
│   ├── google_calendar.py  # Google Calendar API (create/delete events)
│   ├── memory.py           # DynamoDB read/write/delete (with cascade calendar delete)
│   ├── secrets.py          # AWS Secrets Manager (cached across warm invocations)
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

In AWS Console → **Systems Manager → Parameter Store → `/{project-name}/api-keys`**, set the value to:

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
Share your calendar with the service account email and grant it "Make changes to events" permission.

> **Note:** SSM Parameter Store standard tier is free. Secrets Manager costs $0.40/secret/month.

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

| Tool | When Claude uses it | Effect |
|---|---|---|
| `create_calendar_event` | Any message with a date or time | Creates Google Calendar event + saves to DynamoDB (with TTL) |
| `save_memory` | Timeless facts or preferences | Writes to DynamoDB (no expiry) |
| `delete_memory` | "Forget / cancel / delete that" | Removes from DynamoDB + deletes linked Google Calendar event |
| `schedule_study_review` | "I studied X today" / "Day 7 review of X" | Saves study session + schedules future review reminders in calendar |

### Spaced Repetition Logic

| Day reported | Reminders created |
|---|---|
| Day 0 (studied today) | Day 7 review + Day 30 review (parallel calendar events) |
| Day 7 (first review done) | Day 30 review only |
| Day 30 (final review done) | None — topic marked as Mastered in memory |

---

## Memory Data Model (DynamoDB)

| Field | Type | Description |
|---|---|---|
| `id` | String (PK) | UUID |
| `type` | String | `fact` or `event` |
| `label` | String | Human-readable description |
| `date` | String | ISO date if applicable |
| `created_at` | String | ISO timestamp |
| `raw` | String | Original user message |
| `calendar_event_id` | String | Google Calendar event ID (if linked) |
| `expires_at` | Number | Unix timestamp for DynamoDB TTL (calendar-linked items only) |

---

## Potential Future Features

### High value / easy to add

| Feature | Description |
|---|---|
| **Daily briefing** | Scheduled Lambda (EventBridge) that messages you each morning with today's calendar events and any study reviews due |
| **Recurring events** | "Remind me every Monday at 9am to review emails" — uses Google Calendar recurrence rules |
| **Smart search** | "What do I have this week?" — queries DynamoDB by date range instead of dumping all memories |

### Medium effort

| Feature | Description |
|---|---|
| **Habit tracking** | "I went to the gym today" — tracks streaks, reminds you if you miss days |
| **Budget / expense logging** | "Spent £40 on groceries" — stores categorised expenses, can summarise monthly spend |
| **Contact notes** | "John likes coffee, works at Acme, met at conference" — rich people memory beyond just facts |

### Bigger features

| Feature | Description |
|---|---|
| **Voice messages** | Telegram supports audio — transcribe with AWS Transcribe then pass text to Claude as normal |
| **Web search** | Give Claude a search tool (Tavily/Brave API) so it can answer questions beyond its training data |
| **Image understanding** | Telegram lets you send photos — Claude is multimodal, so you could ask "what's in this receipt?" and auto-log expenses |

---

## Model

Uses `claude-sonnet-4-6` — chosen for reliable instruction-following and accurate tool batching (e.g. sending multiple delete calls in one response for parallel execution).
