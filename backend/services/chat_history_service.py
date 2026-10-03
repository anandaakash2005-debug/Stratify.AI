from database.client import table


async def save_chat_message(
    user_id: str,
    report_id: str | None,
    message: str,
    response: str,
    intent: str,
    confidence: float,
):
    return (
        table("chat_history")
        .insert({
            "user_id": user_id,
            "report_id": report_id,
            "message": message,
            "response": response,
            "intent": intent,
            "confidence": confidence,
        })
        .execute()
    )


async def get_chat_history(
    user_id: str,
    limit: int = 50,
):
    result = (
        table("chat_history")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    return result.data or []


async def get_chat_summaries(
    user_id: str,
    limit: int = 50,
):
    """Return grouped summaries with title (first message) and last_message."""
    result = (
        table("chat_history")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    messages = result.data or []

    # Group by report_id, preserving order
    groups: dict[str, list] = {}
    for msg in reversed(messages):
        key = msg.get("report_id") or "general"
        if key not in groups:
            groups[key] = []
        groups[key].append(msg)

    summaries = []
    for key, msgs in groups.items():
        first = msgs[0]
        last = msgs[-1]
        title = first.get("message", "Chat")[:80]
        if len(first.get("message", "")) > 80:
            title += "..."
        summaries.append({
            "id": key,
            "report_id": key if key != "general" else None,
            "title": title,
            "last_message": last.get("response", "")[:120],
            "message_count": len(msgs),
            "created_at": first.get("created_at"),
        })
    return summaries


async def delete_chat_session(
    user_id: str,
):
    return (
        table("chat_history")
        .delete()
        .eq("user_id", user_id)
        .execute()
    )
