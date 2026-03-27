"""
DynamoDB operations for the lunch ideas table.
"""
import os
import uuid
from datetime import datetime, timezone

import boto3

_dynamodb = None


def _get_table():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION_NAME"])
    return _dynamodb.Table(os.environ["LUNCH_IDEAS_TABLE"])


def add(name: str) -> None:
    """Add a lunch idea by name."""
    _get_table().put_item(Item={"id": str(uuid.uuid4()), "name": name})
    print(f"Lunch idea added: {name}")


def remove(name: str) -> bool:
    """Remove a lunch idea by name (case-insensitive). Returns True if found and deleted."""
    table = _get_table()
    items = table.scan().get("Items", [])
    for item in items:
        if item["name"].lower() == name.lower():
            table.delete_item(Key={"id": item["id"]})
            print(f"Lunch idea removed: {name}")
            return True
    return False


def mark_sent(idea_id: str) -> None:
    """Record today as the last time this idea was sent."""
    _get_table().update_item(
        Key={"id": idea_id},
        UpdateExpression="SET last_sent = :date",
        ExpressionAttributeValues={":date": datetime.now(timezone.utc).date().isoformat()},
    )


def load_all() -> list[dict]:
    """Return all saved lunch ideas."""
    return _get_table().scan().get("Items", [])
