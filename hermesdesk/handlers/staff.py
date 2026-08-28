"""Claim a topic and send canned replies."""

from __future__ import annotations

import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import Forbidden
from telegram.ext import ContextTypes
from telegram.helpers import mention_html

from hermesdesk.config import ADMIN_GROUP_ID, ADMIN_USER_IDS
from hermesdesk.db.session import get_session
from hermesdesk.services.canned import (
    delete_reply,
    get_reply,
    list_replies,
    upsert_reply,
    valid_slug,
)
from hermesdesk.services.messages import save_map
from hermesdesk.services.topics import is_topic_closed
from hermesdesk.services.users import (
    claim_label,
    get_user_by_id,
    get_user_by_thread,
    set_blocked,
    set_claim,
)

logger = logging.getLogger("hermesdesk.staff")


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS


def _staff_label(user) -> str:
    return user.full_name or user.username or str(user.id)


async def _topic_user(update: Update):
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


async def claim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await _topic_user(update)
    if target is None:
        return
    actor = update.effective_user
    with get_session() as session:
        db_user = get_user_by_id(session, target.user_id)
        if db_user is None:
            await update.message.reply_html("找不到这个客户。")
            return
        previous = html.escape(claim_label(db_user))
        set_claim(session, db_user, staff_id=actor.id, staff_name=_staff_label(actor))
    extra = "" if previous == "未认领" else f"\n此前由 {previous} 认领。"
    await update.message.reply_html(
        f"{mention_html(actor.id, actor.full_name)} 认领了这个对话。{extra}\n"
        "这是软标记，其他客服仍可以回复。"
    )


async def unclaim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await _topic_user(update)
    if target is None:
        return
    with get_session() as session:
        db_user = get_user_by_id(session, target.user_id)
        if db_user is None:
            await update.message.reply_html("找不到这个客户。")
            return
        set_claim(session, db_user, staff_id=None, staff_name=None)
    await update.message.reply_html("已取消认领，对话回到待领取。")


async def send_canned_body(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    user_id: int,
    thread_id: int,
    body: str,
    slug: str,
) -> str | None:
    try:
        sent_in_topic = await context.bot.send_message(
            ADMIN_GROUP_ID,
            f"{body}",
            message_thread_id=thread_id,
        )
        chat = await context.bot.get_chat(user_id)
        sent_to_user = await chat.send_copy(ADMIN_GROUP_ID, sent_in_topic.message_id)
        with get_session() as session:
            save_map(
                session,
                user_id=user_id,
                user_chat_message_id=sent_to_user.message_id,
                group_chat_message_id=sent_in_topic.message_id,
            )
        return None
    except Forbidden:
        with get_session() as session:
            db_user = get_user_by_id(session, user_id)
            if db_user is not None:
                set_blocked(session, db_user, True)
        return "客户已停用机器人，快捷回复没有发出。"
    except Exception as exc:
        logger.exception("canned reply %s failed", slug)
        return f"发送失败：{html.escape(str(exc))}"


def _reply_keyboard() -> InlineKeyboardMarkup | None:
    with get_session() as session:
        rows = list_replies(session)
        slugs = [item.slug for item in rows]
    if not slugs:
        return None
    buttons = [
        InlineKeyboardButton(slug, callback_data=f"canned_{slug}") for slug in slugs
    ]
    matrix = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(matrix)


async def replies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_html("你没有权限执行此操作。")
        return
    with get_session() as session:
        rows = list_replies(session)
    if not rows:
        await update.message.reply_html(
            "还没有快捷回复。用 <code>/setreply 别名 内容</code> 添加。"
        )
        return
    lines = ["<b>快捷回复</b>"]
    for item in rows:
        preview = item.body.replace("\n", " ")
        if len(preview) > 40:
            preview = preview[:40] + "…"
        lines.append(f"• <code>{html.escape(item.slug)}</code> — {html.escape(preview)}")
    markup = _reply_keyboard() if update.message.message_thread_id else None
    await update.message.reply_html("\n".join(lines), reply_markup=markup)


async def setreply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_html("你没有权限执行此操作。")
        return
    args = list(context.args or [])
    if not args:
        await update.message.reply_html(
            "用法：<code>/setreply 别名 内容</code>\n也可以回复一条消息后只写 <code>/setreply 别名</code>。"
        )
        return
    slug = args[0].lower()
    if not valid_slug(slug):
        await update.message.reply_html("别名只能用 1–32 位字母、数字、下划线或短横线。")
        return
    body = " ".join(args[1:]).strip()
    if not body and update.message.reply_to_message:
        body = (update.message.reply_to_message.text or update.message.reply_to_message.caption or "").strip()
    if not body:
        await update.message.reply_html("请提供回复内容，或回复一条已有消息。")
        return
    if len(body) > 4000:
        await update.message.reply_html("内容太长，请控制在 4000 字以内。")
        return
    with get_session() as session:
        upsert_reply(session, slug, body, update.effective_user.id)
    await update.message.reply_html(
        f"已保存快捷回复 <code>{html.escape(slug)}</code>。\n发送：<code>/reply {html.escape(slug)}</code>"
    )


async def delreply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_html("你没有权限执行此操作。")
        return
    args = list(context.args or [])
    if not args:
        await update.message.reply_html("用法：<code>/delreply 别名</code>")
        return
    slug = args[0].lower()
    with get_session() as session:
        existed = delete_reply(session, slug)
    if existed:
        await update.message.reply_html(f"已删除 <code>{html.escape(slug)}</code>。")
    else:
        await update.message.reply_html(f"没有叫 <code>{html.escape(slug)}</code> 的快捷回复。")


async def reply_canned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await _topic_user(update)
    if target is None:
        return
    args = list(context.args or [])
    if not args:
        await update.message.reply_html("用法：<code>/reply 别名</code>")
        return
    slug = args[0].lower()
    with get_session() as session:
        if is_topic_closed(session, target.message_thread_id):
            await update.message.reply_html("对话已关闭，打开话题后再发送快捷回复。")
            return
        record = get_reply(session, slug)
        if record is None:
            await update.message.reply_html(
                f"没有 <code>{html.escape(slug)}</code>。先看 <code>/replies</code>。"
            )
            return
        body = record.body
        thread_id = target.message_thread_id
        user_id = target.user_id
    error = await send_canned_body(
        context, user_id=user_id, thread_id=thread_id, body=body, slug=slug
    )
    if error:
        await update.message.reply_html(error)


async def canned_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    actor = query.from_user
    if not _is_admin(actor.id):
        await query.answer("没有权限", show_alert=True)
        return
    slug = query.data.split("_", 1)[1].lower()
    thread_id = query.message.message_thread_id if query.message else None
    if not thread_id:
        await query.answer("请在客户话题里点按钮", show_alert=True)
        return
    with get_session() as session:
        target = get_user_by_thread(session, thread_id)
        if target is None:
            await query.answer("这个话题没有绑定客户", show_alert=True)
            return
        if is_topic_closed(session, thread_id):
            await query.answer("对话已关闭", show_alert=True)
            return
        record = get_reply(session, slug)
        if record is None:
            await query.answer("这条快捷回复已删除", show_alert=True)
            return
        body = record.body
        user_id = target.user_id
    error = await send_canned_body(
        context, user_id=user_id, thread_id=thread_id, body=body, slug=slug
    )
    if error:
        await query.answer(error[:180], show_alert=True)
        return
    await query.answer(f"已发送 {slug}")
