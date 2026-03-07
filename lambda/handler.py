"""
Claude Personal Assistant — Lambda Handler
"""

import json
from datetime import datetime, timezone

import claude_client
import google_calendar
import memory
import telegram
from secrets import get_secrets


def lambda_handler(event, context):
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
        reply = _process_message(text, secrets)
    except Exception as e:
        print(f"Unhandled error: {e}")
        reply = "Sorry, something went wrong on my end. Please try again."

    telegram.send_message(secrets["TELEGRAM_BOT_TOKEN"], chat_id, reply)
    return {"statusCode": 200, "body": "ok"}


def _process_message(text, secrets):
    memories = memory.load_all()
    memory_context = memory.format_for_prompt(memories)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    system_prompt = (
        f"You are a helpful personal assistant. Be concise and friendly. "
        f"Today's date is {today}. Use this to resolve relative dates like 'tomorrow', 'next Friday', 'end of month'. "
        f"When the user mentions an appointment, meeting, or event: use create_calendar_event — it saves to memory automatically, do NOT also call save_memory. "
        f"When the user shares personal info or preferences worth remembering (not a calendar event): use save_memory. "
        f"When the user asks to cancel, delete, or forget something: use delete_memory — it will also remove any linked calendar event automatically."
    )
    if memory_context:
        system_prompt += f"\n\n{memory_context}"

    claude = claude_client.get_client()
    messages = [{"role": "user", "content": text}]

    while True:
        response = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            tools=claude_client.TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            reply = next(
                (b.text for b in response.content if b.type == "text"), ""
            )
            print(f"Reply: {reply[:100]}")
            return reply

        # Handle tool calls
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            tool_results.append(_handle_tool(block, text))

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})


def _handle_tool(block, original_text):
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

    except Exception as e:
        print(f"Tool '{block.name}' failed: {e}")
        return {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": f"Error: {e}",
            "is_error": True,
        }
