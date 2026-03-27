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
        "name": "schedule_study_review",
        "description": (
            "Record that the user studied a topic today and schedule spaced-repetition review reminders. "
            "Use when the user says they studied, learned, or revised a topic. "
            "Day 0 = studied today (schedules Day 7 and Day 30 reminders). "
            "Day 7 = completing first review (schedules Day 30 reminder only). "
            "Day 30 = completing final review (marks topic as mastered, no more reminders). "
            "Do NOT use save_memory or create_calendar_event separately for study topics."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic or subject that was studied. e.g. 'Python decorators', 'French vocabulary chapter 3'",
                },
                "day": {
                    "type": "integer",
                    "enum": [0, 7, 30],
                    "description": "Which review day: 0 = first time studied today, 7 = first review, 30 = final review.",
                },
            },
            "required": ["topic", "day"],
        },
    },
    {
        "name": "search_memories",
        "description": (
            "Search saved events and reminders within a date range. "
            "Use this when the user asks about upcoming events or a specific time period — "
            "e.g. 'what do I have this week?', 'what's on next month?', 'any events in March?'. "
            "Always resolve relative dates (today, this week, next month) to ISO dates yourself before calling."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start of date range, ISO format (YYYY-MM-DD), inclusive.",
                },
                "end_date": {
                    "type": "string",
                    "description": "End of date range, ISO format (YYYY-MM-DD), inclusive.",
                },
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "create_recurring_event",
        "description": (
            "Create a recurring Google Calendar event that repeats on a regular schedule. "
            "Use this when the user says something like 'every week', 'every day', 'every month', or 'recurring'. "
            "Do NOT use create_calendar_event for recurring events — use this tool instead. "
            "This saves to memory automatically, so do NOT also call save_memory."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Event title. e.g. 'Weekly team standup'",
                },
                "date": {
                    "type": "string",
                    "description": "ISO date of the first occurrence (YYYY-MM-DD)",
                },
                "frequency": {
                    "type": "string",
                    "enum": ["daily", "weekly", "monthly"],
                    "description": "How often the event repeats.",
                },
                "time": {
                    "type": "string",
                    "description": "Time in HH:MM 24-hour format. Omit for all-day events.",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Duration in minutes for timed events (default 60).",
                },
                "description": {
                    "type": "string",
                    "description": "Optional extra details for the event.",
                },
            },
            "required": ["title", "date", "frequency"],
        },
    },
    {
        "name": "add_lunch_idea",
        "description": (
            "Add a lunch idea to the daily rotation. "
            "Use when the user says something like 'add sushi to my lunch ideas' or 'save pasta as a lunch option'. "
            "Always call this tool exactly ONCE per user request — treat everything the user mentions as a single meal idea."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "A complete meal name, e.g. 'Chicken salad', 'Salmon with roasted vegetables'",
                }
            },
            "required": ["name"],
        },
    },
    {
        "name": "remove_lunch_idea",
        "description": (
            "Remove a lunch idea from the daily rotation. "
            "Use when the user says something like 'remove sushi from my lunch ideas' or 'delete pasta from the list'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the lunch idea to remove.",
                }
            },
            "required": ["name"],
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
    },
]


def get_tools() -> list[dict]:
    """Return TOOLS with cache_control on the last entry."""
    tools = [t.copy() for t in TOOLS]
    tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral"}}
    return tools
