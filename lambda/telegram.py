import json
import urllib.request


def send_message(bot_token: str, chat_id: int, text: str) -> None:
    """Send a text message to a Telegram chat via the Bot API."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req)
