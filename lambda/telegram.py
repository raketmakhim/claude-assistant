import json
import time
import urllib.request

MESSAGE_MAX_AGE_SECONDS = 30


class TelegramMessenger:
    """Messenger implementation for Telegram."""

    def validate_token(self, headers: dict, expected_token: str) -> bool:
        """Return True if the Telegram secret token header matches the expected value."""
        return headers.get("x-telegram-bot-api-secret-token", "") == expected_token

    def parse_update(self, body: str) -> tuple[int | None, str | None]:
        """Parse a Telegram webhook payload and return (chat_id, text).

        Returns (None, None) if the update has no message or no text
        (e.g. photo, sticker, or non-message update types).
        """
        data = json.loads(body or "{}")
        message = data.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        if not chat_id or not text:
            return None, None
        # Discard stale messages from Telegram's retry queue
        if time.time() - message.get("date", 0) > MESSAGE_MAX_AGE_SECONDS:
            print(f"Discarding stale message (age {int(time.time() - message.get('date', 0))}s)")
            return None, None
        return chat_id, text

    def send_message(self, token: str, chat_id: int, text: str) -> None:
        """Send a text message to a Telegram chat via the Bot API."""
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": text}).encode()
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req)
