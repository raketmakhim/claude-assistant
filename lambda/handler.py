"""
Claude Personal Assistant — Lambda Handler
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

import claude_client
import google_calendar
import memory
from messenger import Messenger
from telegram import TelegramMessenger
from secrets import get_secrets

# Swap this line to use a different messaging platform
_messenger: Messenger = TelegramMessenger()


def lambda_handler(event, context):
    """AWS Lambda entry point — receives Telegram webhook and sends a reply.

    Validates the Telegram secret token, parses the incoming message,
    delegates to _process_message, and sends the reply back via Telegram.
    Any unhandled exception is caught here so the bot always sends a response.
    """
    secrets = get_secrets()

    if not _messenger.validate_token(event.get("headers", {}), secrets.get("TELEGRAM_SECRET_TOKEN", "")):
        print("Rejected: invalid secret token")
        return {"statusCode": 403, "body": "Forbidden"}

    chat_id, text = _messenger.parse_update(event.get("body", ""))
    if not chat_id or not text:
        return {"statusCode": 200, "body": "ok"}

    print(f"Message from {chat_id}: {text}")

    try:
        reply = _process_message(text)
    except Exception as e:
        print(f"Unhandled error: {e}")
        reply = "Sorry, something went wrong on my end. Please try again."

    _messenger.send_message(secrets["TELEGRAM_BOT_TOKEN"], chat_id, reply)
    return {"statusCode": 200, "body": "ok"}


def _process_message(text: str) -> str:
    """Run the Claude agentic loop for a single user message and return the reply.

    Loads memories from DynamoDB, builds the system prompt with today's date,
    then repeatedly calls Claude until stop_reason is 'end_turn'. Any tool_use
    blocks returned by Claude are executed in parallel via ThreadPoolExecutor.

    Args:
        text: The raw message text sent by the user via Telegram.
    """
    memories = memory.load_all()
    memory_context = memory.format_for_prompt(memories)

    static_rules = (
        "You are a helpful personal assistant. Be concise and friendly. "
        "Use today's date (provided in the context below) to resolve relative dates like 'tomorrow', 'next Friday', 'end of month'. "
        "CALENDAR RULE: If something involves a date or time — appointments, meetings, reminders, tasks, deadlines, calls — ALWAYS use create_calendar_event. It saves to memory automatically, so do NOT also call save_memory. "
        "MEMORY RULE: Use save_memory only for timeless facts with no specific date — e.g. 'user is vegetarian', 'sister is called Sarah', 'prefers morning calls'. "
        "DELETE RULE: When the user asks to cancel, delete, or forget something: use delete_memory — it will also remove any linked calendar event automatically. "
        "STUDY RULE: When the user says they studied/learned/revised a topic, use schedule_study_review with day=0. If they say they did their Day 7 review, use day=7. Day 30 review, use day=30. Never use save_memory or create_calendar_event for study topics. "
        "SEARCH RULE: When the user asks about events in a specific time period ('what do I have this week', 'anything next month'), use search_memories with the appropriate date range — do not rely on the memory list above. "
        "RECURRING RULE: When the user says 'every week', 'every day', 'every month', or 'recurring', use create_recurring_event instead of create_calendar_event."
    )
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dynamic_memory = f"Today's date: {today}\n\n" + (memory_context if memory_context else "Memory database: empty — nothing saved yet.")

    claude = claude_client.get_client()
    messages = [{"role": "user", "content": text}]
    max_iterations = 10

    for _ in range(max_iterations):
        response = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=[
                {"type": "text", "text": static_rules, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": dynamic_memory},
            ],
            tools=claude_client.get_tools(),
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            reply = next(
                (b.text for b in response.content if b.type == "text"), ""
            )
            print(f"Reply: {reply[:100]}")
            return reply

        # Handle tool calls — run in parallel if multiple blocks
        tool_blocks = [b for b in response.content if b.type == "tool_use"]
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(_handle_tool, block, text, memories) for block in tool_blocks]
            tool_results = [f.result() for f in futures]

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    print(f"Agentic loop exceeded {max_iterations} iterations — aborting")
    return "Sorry, I got stuck processing that. Please try again."


def _handle_tool(block, original_text: str, memories: list[dict]) -> dict:
    """Execute a single Claude tool_use block and return the tool_result dict.

    Handles save_memory, delete_memory, create_calendar_event, search_memories, and schedule_study_review.
    Exceptions are caught and returned as an is_error tool_result so the
    agentic loop can continue and Claude can inform the user of the failure.
    """
    try:
        if block.name == "save_memory":
            inp = block.input
            memory.write(
                label=inp["label"],
                memory_type=inp["type"],
                date=inp.get("date"),
                raw=original_text,
            )
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": f"Saved: {inp['label']}",
            }

        elif block.name == "delete_memory":
            memory.delete(block.input["memory_id"])
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": "Memory deleted (and calendar event removed if one was linked).",
            }

        elif block.name == "create_calendar_event":
            inp = block.input
            result = google_calendar.create_event(
                title=inp["title"],
                date=inp["date"],
                time=inp.get("time"),
                duration_minutes=inp.get("duration_minutes", 60),
                description=inp.get("description"),
            )
            memory.write(
                label=inp["title"] + (f" on {inp['date']}" + (f" at {inp['time']}" if inp.get("time") else "")),
                memory_type="event",
                date=inp["date"],
                raw=original_text,
                calendar_event_id=result.get("id"),
            )
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": f"Calendar event '{inp['title']}' created for {inp['date']} and saved to memory.",
            }

        elif block.name == "create_recurring_event":
            inp = block.input
            result = google_calendar.create_recurring_event(
                title=inp["title"],
                date=inp["date"],
                frequency=inp["frequency"],
                time=inp.get("time"),
                duration_minutes=inp.get("duration_minutes", 60),
                description=inp.get("description"),
            )
            time_str = f" at {inp['time']}" if inp.get("time") else ""
            memory.write(
                label=f"{inp['title']} (every {inp['frequency']}, starting {inp['date']}{time_str})",
                memory_type="fact",
                raw=original_text,
                calendar_event_id=result.get("id"),
            )
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": f"Recurring {inp['frequency']} event '{inp['title']}' created starting {inp['date']} and saved to memory.",
            }

        elif block.name == "search_memories":
            inp = block.input
            start_date = inp.get("start_date")
            end_date = inp.get("end_date")
            results = sorted(
                [
                    m for m in memories
                    if m.get("date")
                    and (not start_date or m["date"] >= start_date)
                    and (not end_date or m["date"] <= end_date)
                ],
                key=lambda m: m["date"],
            )
            if not results:
                content = f"No events found between {inp.get('start_date')} and {inp.get('end_date')}."
            else:
                lines = [f"Events from {inp.get('start_date')} to {inp.get('end_date')}:"]
                for m in results:
                    line = f"- [id:{m['id']}] {m['label']} ({m.get('date', '')})"
                    if m.get("calendar_event_id"):
                        line += " [has calendar event]"
                    lines.append(line)
                content = "\n".join(lines)
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
            }

        elif block.name == "schedule_study_review":
            inp = block.input
            topic = inp["topic"]
            day = inp["day"]

            REVIEW_SCHEDULE = {0: [7, 30], 7: [30], 30: []}
            today = datetime.now(timezone.utc).date()

            # Schedule future review reminders — run in parallel if multiple
            def _create_review(next_day):
                days_to_add = next_day - day
                review_date = (today + timedelta(days=days_to_add)).strftime("%Y-%m-%d")
                review_title = f"Study: {topic} — Day {next_day} review"
                cal_result = google_calendar.create_event(title=review_title, date=review_date)
                memory.write(
                    label=f"{review_title} on {review_date}",
                    memory_type="event",
                    date=review_date,
                    raw=original_text,
                    calendar_event_id=cal_result.get("id"),
                )
                return f"Scheduled: {review_title} on {review_date}"

            results = []

            next_days = REVIEW_SCHEDULE.get(day, [])
            if next_days:
                with ThreadPoolExecutor() as executor:
                    futures = [executor.submit(_create_review, nd) for nd in next_days]
                    results.extend(f.result() for f in futures)

            # Mark as mastered after Day 30
            if day == 30:
                memory.write(label=f"Mastered: {topic}", memory_type="fact", raw=original_text)
                results.append(f"Marked as mastered: {topic}")

            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": "; ".join(results),
            }

    except Exception as e:
        print(f"Tool '{block.name}' failed: {e}")
        return {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": f"Error: {e}",
            "is_error": True,
        }
