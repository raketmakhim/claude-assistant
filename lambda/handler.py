"""
Claude Personal Assistant — Lambda Handler
"""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

import claude_client
import google_calendar
import memory
import telegram
from secrets import get_secrets


def lambda_handler(event, context):
    """AWS Lambda entry point — receives Telegram webhook and sends a reply.

    Validates the Telegram secret token, parses the incoming message,
    delegates to _process_message, and sends the reply back via Telegram.
    Any unhandled exception is caught here so the bot always sends a response.
    """
    secrets = get_secrets()

    # Validate Telegram secret token
    headers = event.get("headers", {})
    token = headers.get("x-telegram-bot-api-secret-token", "")
    if token != secrets.get("TELEGRAM_SECRET_TOKEN", ""):
        print("Rejected: invalid secret token")
        return {"statusCode": 403, "body": "Forbidden"}

    # Parse Telegram update
    body = json.loads(event.get("body", "{}"))
    message = body.get("message", {})

    if not message:
        return {"statusCode": 200, "body": "ok"}

    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if not text or not chat_id:
        return {"statusCode": 200, "body": "ok"}

    print(f"Message from {chat_id}: {text}")

    try:
        reply = _process_message(text)
    except Exception as e:
        print(f"Unhandled error: {e}")
        reply = "Sorry, something went wrong on my end. Please try again."

    telegram.send_message(secrets["TELEGRAM_BOT_TOKEN"], chat_id, reply)
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

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    system_prompt = (
        f"You are a helpful personal assistant. Be concise and friendly. "
        f"Today's date is {today}. Use this to resolve relative dates like 'tomorrow', 'next Friday', 'end of month'. "
        f"CALENDAR RULE: If something involves a date or time — appointments, meetings, reminders, tasks, deadlines, calls — ALWAYS use create_calendar_event. It saves to memory automatically, so do NOT also call save_memory. "
        f"MEMORY RULE: Use save_memory only for timeless facts with no specific date — e.g. 'user is vegetarian', 'sister is called Sarah', 'prefers morning calls'. "
        f"DELETE RULE: When the user asks to cancel, delete, or forget something: use delete_memory — it will also remove any linked calendar event automatically. "
        f"STUDY RULE: When the user says they studied/learned/revised a topic, use schedule_study_review with day=0. If they say they did their Day 7 review, use day=7. Day 30 review, use day=30. Never use save_memory or create_calendar_event for study topics."
    )
    system_prompt += f"\n\n{memory_context}" if memory_context else "\n\nMemory database: empty — nothing saved yet."

    claude = claude_client.get_client()
    messages = [{"role": "user", "content": text}]
    max_iterations = 10

    for _ in range(max_iterations):
        response = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
            tools=claude_client.TOOLS,
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
            futures = [executor.submit(_handle_tool, block, text) for block in tool_blocks]
            tool_results = [f.result() for f in futures]

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    print(f"Agentic loop exceeded {max_iterations} iterations — aborting")
    return "Sorry, I got stuck processing that. Please try again."


def _handle_tool(block, original_text: str) -> dict:
    """Execute a single Claude tool_use block and return the tool_result dict.

    Handles save_memory, delete_memory, and create_calendar_event.
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
