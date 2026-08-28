"""Collect album messages, then copy them as a group."""

from __future__ import annotations

from telegram.ext import ContextTypes

from hermesdesk.config import MEDIA_GROUP_DELAY
from hermesdesk.db.models import MediaGroupMessage, User
from hermesdesk.db.session import get_session
from hermesdesk.services.messages import save_map


async def _send_media_group_later(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    payload = job.data or {}
    media_group_id = str(payload["media_group_id"])
    from_chat_id = int(payload["from_chat_id"])
    target_id = int(payload["target_id"])
    direction = payload["direction"]

    with get_session() as session:
        media_group_msgs = (
            session.query(MediaGroupMessage)
            .filter(
                MediaGroupMessage.media_group_id == media_group_id,
                MediaGroupMessage.chat_id == from_chat_id,
            )
            .order_by(MediaGroupMessage.message_id.asc())
            .all()
        )
        message_ids = [item.message_id for item in media_group_msgs]
        if not message_ids:
            return

        chat = await context.bot.get_chat(target_id)
        if direction == "u2a":
            user = session.query(User).filter(User.user_id == from_chat_id).first()
            if user is None:
                return
            sents = await chat.send_copies(
                from_chat_id,
                message_ids,
                message_thread_id=user.message_thread_id,
            )
            for sent, msg in zip(sents, media_group_msgs):
                save_map(
                    session,
                    user_id=user.user_id,
                    user_chat_message_id=msg.message_id,
                    group_chat_message_id=sent.message_id,
                )
        else:
            sents = await chat.send_copies(from_chat_id, message_ids)
            for sent, msg in zip(sents, media_group_msgs):
                save_map(
                    session,
                    user_id=target_id,
                    user_chat_message_id=sent.message_id,
                    group_chat_message_id=msg.message_id,
                )


async def schedule_media_group(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_id: int,
    target_id: int,
    media_group_id: str | int,
    direction: str,
    delay: float | None = None,
) -> str:
    name = f"sendmediagroup_{chat_id}_{target_id}_{media_group_id}_{direction}"
    context.job_queue.run_once(
        _send_media_group_later,
        delay if delay is not None else MEDIA_GROUP_DELAY,
        chat_id=chat_id,
        name=name,
        data={
            "media_group_id": str(media_group_id),
            "from_chat_id": chat_id,
            "target_id": target_id,
            "direction": direction,
        },
    )
    return name


def store_media_group_message(
    session,
    *,
    chat_id: int,
    message_id: int,
    media_group_id: str | int,
    caption_html: str | None,
) -> None:
    session.add(
        MediaGroupMessage(
            chat_id=chat_id,
            message_id=message_id,
            media_group_id=str(media_group_id),
            is_header=False,
            caption_html=caption_html,
        )
    )
    session.flush()
