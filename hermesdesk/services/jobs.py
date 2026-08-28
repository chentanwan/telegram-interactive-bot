"""Small job helpers."""

from __future__ import annotations

from telegram.ext import ContextTypes


async def _delete_message_cb(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    try:
        await context.bot.delete_message(job.chat_id, job.data)
    except Exception:
        pass


async def delete_message_later(
    delay: float,
    chat_id: int,
    msg_id: int,
    context: ContextTypes.DEFAULT_TYPE,
) -> str:
    name = f"deljob_{chat_id}_{msg_id}"
    context.job_queue.run_once(
        _delete_message_cb,
        delay,
        chat_id=chat_id,
        name=name,
        data=msg_id,
    )
    return name
