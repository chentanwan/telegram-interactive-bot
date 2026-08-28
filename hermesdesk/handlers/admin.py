"""Admin-group handlers: topic events, admin-to-user forwarding, commands."""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.error import Forbidden, RetryAfter
from telegram.ext import ContextTypes

from hermesdesk.config import (
    ADMIN_GROUP_ID,
    ADMIN_USER_IDS,
    BROADCAST_INTERVAL,
    DELETE_USER_MESSAGE_ON_CLEAR_CMD,
)
from hermesdesk.db.session import get_session
from hermesdesk.services.media_group import schedule_media_group, store_media_group_message
from hermesdesk.services.messages import (
    delete_maps_for_user,
    list_user_chat_message_ids,
    save_map,
    user_id_for_group_message,
)
from hermesdesk.services.topics import (
    count_open_topics,
    is_topic_closed,
    reset_user_topic,
    set_topic_status,
)
from hermesdesk.services.users import count_banned, count_users, get_user_by_thread, list_users, upsert_user

logger = logging.getLogger("hermesdesk.admin")


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS


async def forwarding_message_a2u(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message_thread_id = update.message.message_thread_id
    if not message_thread_id:
        return

    with get_session() as session:
        upsert_user(session, user)
        db_user = get_user_by_thread(session, message_thread_id)
        if db_user is None:
            logger.debug("no user bound to thread %s", message_thread_id)
            return
        user_id = db_user.user_id

        if update.message.forum_topic_created:
            set_topic_status(session, message_thread_id, "opened", chat_id=ADMIN_GROUP_ID)
            return
        if update.message.forum_topic_closed:
            set_topic_status(session, message_thread_id, "closed", chat_id=ADMIN_GROUP_ID)
            closed = True
            reopened = False
        elif update.message.forum_topic_reopened:
            set_topic_status(session, message_thread_id, "opened", chat_id=ADMIN_GROUP_ID)
            closed = False
            reopened = True
        else:
            closed = is_topic_closed(session, message_thread_id)
            reopened = False

        reply_to = None
        if update.message.reply_to_message:
            reply_to = user_id_for_group_message(
                session, update.message.reply_to_message.message_id
            )

    if update.message.forum_topic_closed:
        await context.bot.send_message(
            user_id, "对话已经结束。对方已经关闭了对话。你的留言将被忽略。"
        )
        return
    if reopened:
        await context.bot.send_message(user_id, "对方重新打开了对话。可以继续对话了。")
        return
    if closed:
        await update.message.reply_html("对话已经结束。希望和对方联系，需要打开对话。")
        return

    params = {}
    if reply_to:
        params["reply_to_message_id"] = reply_to

    try:
        if update.message.media_group_id:
            with get_session() as session:
                store_media_group_message(
                    session,
                    chat_id=update.message.chat.id,
                    message_id=update.message.message_id,
                    media_group_id=update.message.media_group_id,
                    caption_html=update.message.caption_html,
                )
            current = context.application.user_data[user_id].get("current_media_group_id")
            if str(update.message.media_group_id) != str(current or 0):
                context.application.user_data[user_id]["current_media_group_id"] = str(
                    update.message.media_group_id
                )
                await schedule_media_group(
                    context,
                    chat_id=update.effective_chat.id,
                    target_id=user_id,
                    media_group_id=update.message.media_group_id,
                    direction="a2u",
                )
            return

        chat = await context.bot.get_chat(user_id)
        sent_msg = await chat.send_copy(
            update.effective_chat.id, update.message.id, **params
        )
        with get_session() as session:
            save_map(
                session,
                user_id=user_id,
                group_chat_message_id=update.message.id,
                user_chat_message_id=sent_msg.message_id,
            )
    except Exception as exc:
        logger.exception("a2u forward failed")
        await update.message.reply_html(f"发送失败: {exc}\n")


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not _is_admin(user.id):
        await update.message.reply_html("你没有权限执行此操作。")
        return
    if not update.message.message_thread_id:
        await update.message.reply_html("请在客户话题内使用 /clear。")
        return

    thread_id = update.message.message_thread_id
    await context.bot.delete_forum_topic(update.effective_chat.id, thread_id)

    with get_session() as session:
        target_user = get_user_by_thread(session, thread_id)
        if target_user is None:
            return
        user_id = target_user.user_id
        message_ids = (
            list_user_chat_message_ids(session, user_id)
            if DELETE_USER_MESSAGE_ON_CLEAR_CMD
            else []
        )
        delete_maps_for_user(session, user_id)
        reset_user_topic(session, target_user)

    if message_ids:
        try:
            await context.bot.delete_messages(user_id, message_ids)
        except Exception as exc:
            logger.warning("failed to delete user-side messages: %s", exc)


async def _broadcast(context: ContextTypes.DEFAULT_TYPE) -> None:
    payload = context.job.data or {}
    msg_id = int(payload["msg_id"])
    chat_id = int(payload["chat_id"])
    requester_id = int(payload["requester_id"])
    thread_id = payload.get("thread_id")

    with get_session() as session:
        users = list_users(session)
        user_ids = [item.user_id for item in users if not item.is_banned]

    success = 0
    failed = 0
    blocked = 0
    for user_id in user_ids:
        try:
            chat = await context.bot.get_chat(user_id)
            await chat.send_copy(chat_id, msg_id)
            success += 1
        except Forbidden:
            blocked += 1
        except RetryAfter as exc:
            await asyncio.sleep(exc.retry_after + 0.5)
            try:
                chat = await context.bot.get_chat(user_id)
                await chat.send_copy(chat_id, msg_id)
                success += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1
        if BROADCAST_INTERVAL > 0:
            await asyncio.sleep(BROADCAST_INTERVAL)

    summary = (
        f"广播完成。\n成功 {success} / 失败 {failed} / 拉黑或停用 {blocked}。"
    )
    try:
        await context.bot.send_message(
            chat_id,
            summary,
            message_thread_id=thread_id,
        )
    except Exception:
        await context.bot.send_message(requester_id, summary)


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not _is_admin(user.id):
        await update.message.reply_html("你没有权限执行此操作。")
        return
    if not update.message.reply_to_message:
        await update.message.reply_html(
            "这条指令需要回复一条消息，被回复的消息将被广播。"
        )
        return

    context.job_queue.run_once(
        _broadcast,
        0,
        data={
            "msg_id": update.message.reply_to_message.id,
            "chat_id": update.effective_chat.id,
            "requester_id": user.id,
            "thread_id": update.message.message_thread_id,
        },
    )
    await update.message.reply_html("广播已加入队列，完成后会回执结果。")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not _is_admin(user.id):
        await update.message.reply_html("你没有权限执行此操作。")
        return

    with get_session() as session:
        total = count_users(session)
        banned = count_banned(session)
        opened = count_open_topics(session)

    queued = len(context.job_queue.jobs()) if context.job_queue else 0
    await update.message.reply_html(
        f"<b>HermesDesk 状态</b>\n"
        f"用户总数：{total}\n"
        f"封禁用户：{banned}\n"
        f"开放话题：{opened}\n"
        f"后台任务：{queued}"
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update: %s", context.error)
    logger.debug("Exception detail is :", exc_info=context.error)
    try:
        text = f"⚠️ HermesDesk 捕获到异常：{context.error}"
        await context.bot.send_message(ADMIN_GROUP_ID, text[:3500])
    except Exception:
        pass
