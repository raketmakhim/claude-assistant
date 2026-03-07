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
            "Create an event on Google Calendar and save it to memory. "
            "Use this when the user wants to be reminded of something or add an event to their calendar. "
            "Always resolve the date and time yourself — never ask the user for a formatted date. "
            "This automatically saves to memory too, so do NOT separately call save_memory for calendar events."
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
            "Save an important fact or reminder to long-term memory (not a calendar event). "
            "Use this for personal info, preferences, and facts worth remembering — "
            "e.g. 'user is vegetarian', 'sister's name is Sarah', 'prefers morning calls'. "
            "Do NOT use this for calendar events — create_calendar_event handles memory for those automatically."
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
                    "enum": ["reminder", "event", "fact"],
                    "description": "reminder = action to take, event = date/occasion, fact = general info",
                },
                "date": {
                    "type": "string",
                    "description": "ISO date if applicable (YYYY-MM-DD)",
                },
            },
            "required": ["label", "type"],
        },
    },
]
