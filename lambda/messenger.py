"""Messenger protocol — defines the interface any messaging platform must implement."""

from typing import Protocol


class Messenger(Protocol):
    """Interface for a messaging platform.

    Implement this to swap Telegram for any other platform (WhatsApp, Discord, etc.)
    without touching handler.py.
    """

    def validate_token(self, headers: dict, expected_token: str) -> bool:
        """Return True if the incoming request is authenticated."""
        ...

    def parse_update(self, body: str) -> tuple[int | None, str | None]:
        """Parse a webhook payload and return (chat_id, text).

        Return (None, None) if the update contains no actionable message.
        """
        ...

    def send_message(self, token: str, chat_id: int, text: str) -> None:
        """Send a text reply to the user."""
        ...
