"""Admin-group handlers: topic events, admin-to-user forwarding, commands."""

from __future__ import annotations

import asyncio
import html
import logging
from types import SimpleNamespace

from telegram import Update
from telegram.error import Forbidden, RetryAfter
from telegram.ext import ContextTypes
from telegram.helpers import mention_html

from hermesdesk.config import (
    ADMIN_GROUP_ID,
    ADMIN_USER_IDS,
    BROADCAST_INTERVAL,
    DELETE_USER_MESSAGE_ON_CLEAR_CMD,
)
from hermesdesk.db.models import User
from hermesdesk.db.session import get_session
from hermesdesk.handlers.user import send_contact_card
from hermesdesk.services.media_group import schedule_media_group, store_media_group_message
from hermesdesk.services.messages import (
    delete_maps_for_user,
    list_user_chat_message_ids,
    save_map,
    user_id_for_group_message,
)
from hermesdesk.services.topics import (
    count_open_topics,
    get_topic_status,
    is_topic_closed,
    reset_user_topic,
    set_topic_status,
)
from hermesdesk.services.users import (
    count_banned,
    count_blocked,
    count_users,
    get_user_by_id,
    get_user_by_thread,
    list_broadcast_targets,
    mark_blocked_by_ids,
    set_banned,
    set_blocked,
    set_note,
    upsert_user,
)

logger = logging.getLogger("hermesdesk.admin")


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS


def _format_time(value) -> str:
    if not value:
        return "无"
    try:
        if getattr(value, "tzinfo", None) is not None:
            value = value.astimezone()
        return value.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(value)


def _card_user(db_user: User) -> SimpleNamespace:
    return SimpleNamespace(
        id=db_user.user_id,
        first_name=db_user.first_name or str(db_user.user_id),
        last_name=db_user.last_name or "",
        username=db_user.username,
        is_premium=bool(db_user.is_premium),
    )


def _display_name(db_user: User) -> str:
    first = db_user.first_name or ""
    last = db_user.last_name or ""
    full = f"{first} {last}".strip() or str(db_user.user_id)
    return mention_html(db_user.user_id, full)


async def _require_staff_topic_user(update: Update) -> User | None:
    actor = update.effective_user
    if not _is_admin(actor.id):
        await update.message.reply_html("你没有权限执行此操作。")
        return None
    thread_id = update.message.message_thread_id
    if not thread_id:
        await update.message.reply_html("请在客户话题内使用这条命令。")
        return None
    with get_session() as session:
        target = get_user_by_thread(session, thread_id)
        if target is None:
            await update.message.reply_html("这个话题没有绑定客户。")
            return None
        session.expunge(target)
        return target


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
    except Forbidden:
        with get_session() as session:
            db_user = get_user_by_id(session, user_id)
            if db_user is not None:
                set_blocked(session, db_user, True)
        await update.message.reply_html(
            "发送失败：客户已停用机器人。已标记为停用，下次广播会跳过。"
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
        user_ids = [item.user_id for item in list_broadcast_targets(session)]

    success = 0
    failed = 0
    blocked = 0
    newly_blocked: list[int] = []
    for user_id in user_ids:
        try:
            chat = await context.bot.get_chat(user_id)
            await chat.send_copy(chat_id, msg_id)
            success += 1
        except Forbidden:
            blocked += 1
            newly_blocked.append(user_id)
        except RetryAfter as exc:
            await asyncio.sleep(exc.retry_after + 0.5)
            try:
                chat = await context.bot.get_chat(user_id)
                await chat.send_copy(chat_id, msg_id)
                success += 1
            except Forbidden:
                blocked += 1
                newly_blocked.append(user_id)
            except Exception:
                failed += 1
        except Exception:
            failed += 1
        if BROADCAST_INTERVAL > 0:
            await asyncio.sleep(BROADCAST_INTERVAL)

    if newly_blocked:
        with get_session() as session:
            mark_blocked_by_ids(session, newly_blocked)

    summary = (
        f"广播完成。\n成功 {success} / 失败 {failed} / 停用机器人 {blocked}。"
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
        blocked = count_blocked(session)
        opened = count_open_topics(session)

    queued = len(context.job_queue.jobs()) if context.job_queue else 0
    await update.message.reply_html(
        f"<b>HermesDesk 状态</b>\n"
        f"用户总数：{total}\n"
        f"封禁用户：{banned}\n"
        f"停用机器人：{blocked}\n"
        f"开放话题：{opened}\n"
        f"后台任务：{queued}"
    )


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await _require_staff_topic_user(update)
    if target is None:
        return
    with get_session() as session:
        db_user = get_user_by_id(session, target.user_id)
        if db_user is None:
            await update.message.reply_html("找不到这个客户。")
            return
        set_banned(session, db_user, True)
        name = _display_name(db_user)
    try:
        await context.bot.send_message(target.user_id, "你已被客服封禁，暂时无法继续对话。")
    except Exception as exc:
        logger.info("could not notify banned user %s: %s", target.user_id, exc)
    await update.message.reply_html(
        f"已封禁 {name}。客户无法再发消息进来，话题可以保留作记录。"
    )


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await _require_staff_topic_user(update)
    if target is None:
        return
    with get_session() as session:
        db_user = get_user_by_id(session, target.user_id)
        if db_user is None:
            await update.message.reply_html("找不到这个客户。")
            return
        set_banned(session, db_user, False)
        set_blocked(session, db_user, False)
        name = _display_name(db_user)
    try:
        await context.bot.send_message(target.user_id, "客服已解除对你的限制，可以继续发送消息。")
    except Exception as exc:
        logger.info("could not notify unbanned user %s: %s", target.user_id, exc)
    await update.message.reply_html(f"已解封 {name}，并清除停用标记。")


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await _require_staff_topic_user(update)
    if target is None:
        return

    with get_session() as session:
        db_user = get_user_by_id(session, target.user_id)
        if db_user is None:
            await update.message.reply_html("找不到这个客户。")
            return
        topic = get_topic_status(session, db_user.message_thread_id or 0)
        topic_state = topic.status if topic else "无话题"
        note_text = db_user.note or "无"
        card = _card_user(db_user)
        text = (
            f"<b>客户资料</b>\n"
            f"用户：{_display_name(db_user)}\n"
            f"ID：<code>{db_user.user_id}</code>\n"
            f"用户名：@{html.escape(db_user.username) if db_user.username else '无'}\n"
            f"会员：{'Premium' if db_user.is_premium else '普通'}\n"
            f"封禁：{'是' if db_user.is_banned else '否'}\n"
            f"停用机器人：{'是' if db_user.is_blocked else '否'}\n"
            f"话题：{topic_state}（{db_user.message_thread_id or 0}）\n"
            f"最近出现：{_format_time(db_user.last_seen_at)}\n"
            f"建档：{_format_time(db_user.created_at)}\n"
            f"备注：{html.escape(note_text)}"
        )
        thread_id = db_user.message_thread_id

    await update.message.reply_html(text)
    if thread_id:
        try:
            await send_contact_card(update.effective_chat.id, thread_id, card, context)
        except Exception as exc:
            logger.info("could not refresh contact card: %s", exc)


async def note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await _require_staff_topic_user(update)
    if target is None:
        return

    raw = " ".join(context.args).strip() if context.args else ""
    if not raw and update.message.reply_to_message and update.message.reply_to_message.text:
        raw = update.message.reply_to_message.text.strip()

    with get_session() as session:
        db_user = get_user_by_id(session, target.user_id)
        if db_user is None:
            await update.message.reply_html("找不到这个客户。")
            return
        if not raw or raw in {"-", "clear", "删除"}:
            set_note(session, db_user, None)
            await update.message.reply_html("已清空该客户的备注。")
            return
        if len(raw) > 4000:
            await update.message.reply_html("备注太长，请控制在 4000 字以内。")
            return
        set_note(session, db_user, raw)
        name = _display_name(db_user)

    await update.message.reply_html(
        f"已记下 {name} 的备注（仅客服可见）：\n{html.escape(raw)}"
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update: %s", context.error)
    logger.debug("Exception detail is :", exc_info=context.error)
    try:
        text = f"⚠️ HermesDesk 捕获到异常：{context.error}"
        await context.bot.send_message(ADMIN_GROUP_ID, text[:3500])
    except Exception:
        pass
