"""Bidirectional edited-message sync."""

from __future__ import annotations

import logging

from telegram import Message, Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

from hermesdesk.config import ADMIN_GROUP_ID
from hermesdesk.db.session import get_session
from hermesdesk.services.messages import get_map_by_group_message, get_map_by_user_message
from hermesdesk.services.topics import is_topic_closed
from hermesdesk.services.users import get_user_by_id, get_user_by_thread, set_blocked

logger = logging.getLogger("hermesdesk.sync")


async def apply_edit(bot, chat_id: int, message_id: int, source: Message) -> bool:
    try:
        if source.text is not None:
            await bot.edit_message_text(
                text=source.text_html,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return True
        if source.caption is not None:
            await bot.edit_message_caption(
                caption=source.caption_html,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML",
            )
            return True
    except BadRequest as exc:
        text = str(exc).lower()
        if "message is not modified" in text:
            return True
        logger.info("edit failed chat=%s msg=%s: %s", chat_id, message_id, exc)
        return False
    except Forbidden:
        raise
    except Exception:
        logger.exception("edit failed chat=%s msg=%s", chat_id, message_id)
        return False
    return False


async def edited_message_u2a(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.edited_message
    if message is None:
        return
    user = update.effective_user
    if user is None:
        return

    with get_session() as session:
        db_user = get_user_by_id(session, user.id)
        if db_user is None or db_user.is_banned:
            return
        if is_topic_closed(session, db_user.message_thread_id):
            return
        record = get_map_by_user_message(session, message.message_id, user.id)
        if record is None:
            return
        target_id = record.group_chat_message_id

    try:
        await apply_edit(context.bot, ADMIN_GROUP_ID, target_id, message)
    except Forbidden:
        logger.info("cannot edit group copy for user %s", user.id)


async def edited_message_a2u(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.edited_message
    if message is None or not message.message_thread_id:
        return

    with get_session() as session:
        db_user = get_user_by_thread(session, message.message_thread_id)
        if db_user is None:
            return
        if is_topic_closed(session, message.message_thread_id):
            return
        record = get_map_by_group_message(session, message.message_id)
        if record is None:
            return
        user_id = record.user_id
        target_id = record.user_chat_message_id

    try:
        await apply_edit(context.bot, user_id, target_id, message)
    except Forbidden:
        with get_session() as session:
            db_user = get_user_by_id(session, user_id)
            if db_user is not None:
                set_blocked(session, db_user, True)
        logger.info("customer %s blocked the bot during edit sync", user_id)
