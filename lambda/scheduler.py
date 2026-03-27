"""
Daily lunch idea scheduler — triggered by EventBridge, no Claude involved.
Picks a random lunch idea from DynamoDB and sends it to Telegram.

Selection logic:
- Prefer ideas not sent in the last 7 days (or never sent)
- If all ideas were sent within 7 days (small list), fall back to the least recently sent
"""
import random
from datetime import date, timedelta

import lunch_ideas
import memory
from secrets import get_secrets
from telegram import TelegramMessenger

_messenger = TelegramMessenger()
_COOLDOWN_DAYS = 7


def lambda_handler(event, context):
    secrets = get_secrets()
    chat_id = memory.load_chat_id()
    if not chat_id:
        print("No chat ID saved yet — skipping")
        return {"statusCode": 200, "body": "no chat id"}

    ideas = lunch_ideas.load_all()
    if not ideas:
        print("No lunch ideas saved — skipping")
        return {"statusCode": 200, "body": "no ideas"}

    cutoff = (date.today() - timedelta(days=_COOLDOWN_DAYS)).isoformat()
    candidates = [i for i in ideas if not i.get("last_sent") or i["last_sent"] < cutoff]

    if not candidates:
        # All sent within cooldown window — exclude only the most recent to avoid repeats, pick randomly from the rest
        most_recent_id = max(ideas, key=lambda i: i.get("last_sent", ""))["id"]
        candidates = [i for i in ideas if i["id"] != most_recent_id] or ideas

    idea = random.choice(candidates)
    lunch_ideas.mark_sent(idea["id"])
    _messenger.send_message(secrets["TELEGRAM_BOT_TOKEN"], chat_id, f"Today's lunch idea: {idea['name']}")
    print(f"Sent lunch idea: {idea['name']}")
    return {"statusCode": 200, "body": "sent"}
