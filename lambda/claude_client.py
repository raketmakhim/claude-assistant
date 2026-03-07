import anthropic

from secrets import get_secrets

_claude_client = None


def get_client() -> anthropic.Anthropic:
    """Return a cached Anthropic client, initialised with the API key from Secrets Manager."""
    global _claude_client
    if _claude_client is None:
        secrets = get_secrets()
        _claude_client = anthropic.Anthropic(api_key=secrets["CLAUDE_API_KEY"])
    return _claude_client


TOOLS = [
    {
        "name": "delete_memory",
        "description": (
            "Delete a memory — and its linked Google Calendar event if one exists. "
            "Use this when the user says something like 'forget that', 'remove that reminder', "
            "'cancel that appointment', or 'delete that event'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": "The id of the memory to delete (from the id: prefix in the memory list)",
                }
            },
            "required": ["memory_id"],
        },
    },
    {
        "name": "create_calendar_event",
        "description": (
            "Create a Google Calendar event and save it to memory. "
            "Use this for ANYTHING with a date or time: appointments, meetings, reminders, tasks, calls, deadlines — if it has a date, it goes here. "
            "Always resolve the date and time yourself from context — never ask the user for a formatted date. "
            "This saves to memory automatically, so do NOT also call save_memory."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Event title. e.g. 'Dentist appointment' or 'Team standup'",
                },
                "date": {
                    "type": "string",
                    "description": "ISO date (YYYY-MM-DD)",
                },
                "time": {
                    "type": "string",
                    "description": "Time in HH:MM 24-hour format (e.g. '15:00' for 3pm). Omit for all-day events.",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Duration in minutes for timed events (default 60). e.g. 30 for a half-hour call, 90 for a long meeting.",
                },
                "description": {
                    "type": "string",
                    "description": "Optional extra details for the event",
                },
            },
            "required": ["title", "date"],
        },
    },
    {
        "name": "save_memory",
        "description": (
            "Save a timeless fact about the user — something with no specific date. "
            "e.g. 'user is vegetarian', 'sister is called Sarah', 'prefers morning calls'. "
            "Do NOT use this for anything with a date or time — use create_calendar_event instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Clear description of what to remember. e.g. 'User is vegetarian'",
                },
                "type": {
                    "type": "string",
                    "enum": ["fact"],
                    "description": "Always 'fact' — timeless personal info with no date.",
                },
                "date": {
                    "type": "string",
                    "description": "ISO date if applicable (YYYY-MM-DD)",
                },
            },
            "required": ["label", "type"],
        },
        "cache_control": {"type": "ephemeral"},
    },
]
