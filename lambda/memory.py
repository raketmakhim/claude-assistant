import os
import uuid
from datetime import datetime, timezone, timedelta

import boto3

import google_calendar

_dynamodb = None


def get_dynamodb():
    """Return a cached boto3 DynamoDB resource."""
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION_NAME"])
    return _dynamodb


def load_all() -> list[dict]:
    """Return all memory items from DynamoDB."""
    table = get_dynamodb().Table(os.environ["DYNAMODB_TABLE"])
    response = table.scan()
    return response.get("Items", [])


def write(label: str, memory_type: str, date: str | None = None, raw: str | None = None, calendar_event_id: str | None = None) -> dict:
    """Save a new memory item to DynamoDB and return the stored item.

    Args:
        label: Human-readable description of what to remember.
        memory_type: One of 'fact', 'event', or 'reminder'.
        date: Optional ISO date (YYYY-MM-DD) associated with this memory.
        raw: Original user message that triggered the save.
        calendar_event_id: Google Calendar event ID, if a calendar event was created.
    """
    table = get_dynamodb().Table(os.environ["DYNAMODB_TABLE"])
    item = {
        "id": str(uuid.uuid4()),
        "type": memory_type,
        "label": label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "raw": raw or label,
    }
    if date:
        item["date"] = date
    if calendar_event_id:
        item["calendar_event_id"] = calendar_event_id
        if date:
            # Auto-expire calendar events from memory 1 day after the event date
            event_dt = datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)
            item["expires_at"] = int(event_dt.timestamp())
    table.put_item(Item=item)
    print(f"Memory saved: {label}")
    return item


def delete(memory_id: str) -> None:
    """Delete a memory item from DynamoDB.

    If the item has a linked Google Calendar event (calendar_event_id),
    that event is also deleted before removing the DynamoDB record.
    Calendar deletion failures are logged but do not block the memory deletion.
    """
    table = get_dynamodb().Table(os.environ["DYNAMODB_TABLE"])
    response = table.get_item(Key={"id": memory_id})
    item = response.get("Item")
    if item and item.get("calendar_event_id"):
        try:
            google_calendar.delete_event(item["calendar_event_id"])
        except Exception as e:
            print(f"Warning: could not delete calendar event: {e}")
    table.delete_item(Key={"id": memory_id})
    print(f"Memory deleted: {memory_id}")



_CONVERSATION_ID = "__conversation__"


def save_last_conversation(user_msg: str, assistant_reply: str) -> None:
    """Overwrite the single last-conversation item in DynamoDB."""
    table = get_dynamodb().Table(os.environ["DYNAMODB_TABLE"])
    table.put_item(Item={
        "id": _CONVERSATION_ID,
        "type": "conversation",
        "user": user_msg,
        "assistant": assistant_reply,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


def load_last_conversation() -> dict | None:
    """Return the last conversation item, or None if none exists."""
    table = get_dynamodb().Table(os.environ["DYNAMODB_TABLE"])
    response = table.get_item(Key={"id": _CONVERSATION_ID})
    return response.get("Item")


def format_for_prompt(memories: list[dict]) -> str:
    """Format memories for inclusion in the Claude system prompt.

    Facts (no date) are always included. Past events (date before today)
    are omitted — only upcoming events are shown.
    """
    if not memories:
        return ""
    today = datetime.now(timezone.utc).date().isoformat()
    lines = ["Things I remember about you (ID shown for deletion reference):"]
    for m in memories:
        if m.get("type") == "conversation":
            continue
        item_date = m.get("date")
        if item_date and item_date < today:
            continue  # skip past events
        line = f"- [id:{m['id']}] {m['label']}"
        if item_date:
            line += f" ({item_date})"
        if m.get("calendar_event_id"):
            line += " [has calendar event]"
        lines.append(line)
    if len(lines) == 1:
        return ""  # only header, no items passed the filter
    return "\n".join(lines)
