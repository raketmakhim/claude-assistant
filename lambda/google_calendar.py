from datetime import datetime, timedelta

from googleapiclient.discovery import build
from google.oauth2 import service_account

from secrets import get_secrets

_calendar_service = None


def get_calendar_service():
    """Return a cached Google Calendar API service client.

    Authenticates using the service account JSON stored in Secrets Manager.
    The service account must have been granted access to the target calendar.
    """
    global _calendar_service
    if _calendar_service is None:
        secrets = get_secrets()
        service_account_info = secrets["GOOGLE_SERVICE_ACCOUNT"]
        creds = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        _calendar_service = build("calendar", "v3", credentials=creds)
    return _calendar_service


def create_event(title: str, date: str, time: str | None = None, duration_minutes: int = 60, description: str | None = None, reminder_minutes: int = 60) -> dict:
    """Create a Google Calendar event and return the API response.

    Creates a timed event if `time` is provided (HH:MM, 24-hour), otherwise
    creates an all-day event. Duration only applies to timed events.
    The calendar is identified by GOOGLE_CALENDAR_ID in Secrets Manager.

    Args:
        title: Event summary shown in the calendar.
        date: ISO date string (YYYY-MM-DD).
        time: Optional start time in HH:MM 24-hour format.
        duration_minutes: Length of a timed event in minutes (default 60).
        description: Optional event body text.
        reminder_minutes: Minutes before the event to trigger a popup reminder.
    """
    service = get_calendar_service()
    secrets = get_secrets()
    calendar_id = secrets.get("GOOGLE_CALENDAR_ID", "primary")

    if time:
        start_dt = datetime.strptime(f"{date}T{time}:00", "%Y-%m-%dT%H:%M:%S")
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        event = {
            "summary": title,
            "start": {"dateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "Europe/London"},
            "end": {"dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "Europe/London"},
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": reminder_minutes}],
            },
        }
    else:
        event = {
            "summary": title,
            "start": {"date": date},
            "end": {"date": date},
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": reminder_minutes}],
            },
        }

    if description:
        event["description"] = description

    result = service.events().insert(calendarId=calendar_id, body=event, sendUpdates="none").execute()
    print(f"Calendar event created: {result.get('htmlLink')}")
    return result


def delete_event(calendar_event_id: str) -> None:
    """Permanently delete a Google Calendar event by its event ID."""
    service = get_calendar_service()
    secrets = get_secrets()
    calendar_id = secrets.get("GOOGLE_CALENDAR_ID", "primary")
    service.events().delete(calendarId=calendar_id, eventId=calendar_event_id).execute()
    print(f"Calendar event deleted: {calendar_event_id}")
