"""Private-chat handlers: start, captcha gate, user-to-admin forwarding."""

from __future__ import annotations

import logging
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from telegram.helpers import mention_html

from hermesdesk.config import (
    ADMIN_GROUP_ID,
    ADMIN_USER_IDS,
    APP_NAME,
    DELETE_TOPIC_AS_FOREVER_BAN,
    DISABLE_CAPTCHA,
    MESSAGE_INTERVAL,
    WELCOME_MESSAGE,
)
from hermesdesk.db.session import get_session
from hermesdesk.handlers.captcha import ensure_human
from hermesdesk.services.media_group import schedule_media_group, store_media_group_message
from hermesdesk.services.messages import group_id_for_user_message, save_map
from hermesdesk.services.topics import is_topic_closed, reset_user_topic, set_topic_status
from hermesdesk.services.users import get_user_by_id, set_blocked, upsert_user

logger = logging.getLogger("hermesdesk.user")


async def send_contact_card(chat_id, message_thread_id, user, context: ContextTypes.DEFAULT_TYPE) -> None:
    buttons = [
        [
            InlineKeyboardButton(
                "🏆 高级会员" if user.is_premium else "✈️ 普通会员",
                url="https://t.me/premium",
            )
        ]
    ]
    if user.username:
        buttons.append(
            [InlineKeyboardButton("👤 直接联络", url=f"https://t.me/{user.username}")]
        )

    user_photo = await context.bot.get_user_profile_photos(user.id)
    caption = (
        f"👤 {mention_html(user.id, user.first_name)}\n\n"
        f"📱 {user.id}\n\n"
        f"🔗 @{user.username if user.username else '无'}"
    )
    if user_photo.total_count:
        pic = user_photo.photos[0][-1].file_id
        await context.bot.send_photo(
            chat_id,
            photo=pic,
            caption=caption,
            message_thread_id=message_thread_id,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML",
        )
        return

    await context.bot.send_contact(
        chat_id,
        phone_number="11111",
        first_name=user.first_name,
        last_name=user.last_name or "",
        message_thread_id=message_thread_id,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    with get_session() as session:
        upsert_user(session, user)

    if user.id in ADMIN_USER_IDS:
        logger.info("admin %s(%s) started the bot", user.first_name, user.id)
        try:
            bg = await context.bot.get_chat(ADMIN_GROUP_ID)
            if bg.type not in {"supergroup", "group"}:
                raise RuntimeError(f"后台群类型异常: {bg.type}")
        except Exception as exc:
            logger.error("admin group error: %s", exc)
            await update.message.reply_html(
                "⚠️⚠️后台管理群组设置错误，请检查配置。⚠️⚠️\n"
                f"你需要确保已经将机器人 @{context.bot.username} 邀请入管理群组并且给与了管理员权限。\n"
                f"错误细节：{exc}\n"
            )
            return
        await update.message.reply_html(
            f"你好管理员 {user.first_name}({user.id})\n\n"
            f"欢迎使用 {APP_NAME}。\n\n"
            f"目前配置看起来正常，可以在群组 <b>{bg.title}</b> 中接待客户。"
        )
        return

    await update.message.reply_html(
        f"{mention_html(user.id, user.full_name)} 同学：\n\n{WELCOME_MESSAGE}"
    )


async def forwarding_message_u2a(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not DISABLE_CAPTCHA and not await ensure_human(update, context):
        return

    if MESSAGE_INTERVAL:
        last = context.user_data.get("last_message_time", 0)
        if last > time.time() - MESSAGE_INTERVAL:
            await update.message.reply_html("请不要频繁发送消息。")
            return
        context.user_data["last_message_time"] = time.time()

    user = update.effective_user
    chat_id = ADMIN_GROUP_ID

    with get_session() as session:
        db_user = upsert_user(session, user)
        if db_user.is_blocked:
            set_blocked(session, db_user, False)
        if db_user.is_banned:
            await update.message.reply_html("你已被客服封禁，暂时无法继续对话。")
            return
        message_thread_id = db_user.message_thread_id
        if is_topic_closed(session, message_thread_id):
            await update.message.reply_html(
                "客服已经关闭对话。如需联系，请利用其他途径联络客服回复和你的对话。"
            )
            return
        reply_to = None
        if update.message.reply_to_message:
            reply_to = group_id_for_user_message(
                session,
                update.message.reply_to_message.message_id,
                user.id,
            )

    if not message_thread_id:
        formn = await context.bot.create_forum_topic(
            chat_id,
            name=f"{user.full_name}|{user.id}",
        )
        message_thread_id = formn.message_thread_id
        with get_session() as session:
            db_user = get_user_by_id(session, user.id)
            if db_user is not None:
                db_user.message_thread_id = message_thread_id
            set_topic_status(session, message_thread_id, "opened", chat_id=chat_id)

        await context.bot.send_message(
            chat_id,
            f"新的用户 {mention_html(user.id, user.full_name)} 开始了一个新的会话。",
            message_thread_id=message_thread_id,
            parse_mode="HTML",
        )
        await send_contact_card(chat_id, message_thread_id, user, context)

    params = {"message_thread_id": message_thread_id}
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
            current = context.user_data.get("current_media_group_id")
            if str(update.message.media_group_id) != str(current or 0):
                context.user_data["current_media_group_id"] = str(
                    update.message.media_group_id
                )
                await schedule_media_group(
                    context,
                    chat_id=user.id,
                    target_id=chat_id,
                    media_group_id=update.message.media_group_id,
                    direction="u2a",
                )
            return

        chat = await context.bot.get_chat(chat_id)
        sent_msg = await chat.send_copy(
            update.effective_chat.id, update.message.id, **params
        )
        with get_session() as session:
            save_map(
                session,
                user_id=user.id,
                user_chat_message_id=update.message.id,
                group_chat_message_id=sent_msg.message_id,
            )
    except BadRequest:
        with get_session() as session:
            db_user = get_user_by_id(session, user.id)
            if db_user is None:
                return
            if DELETE_TOPIC_AS_FOREVER_BAN:
                db_user.is_banned = True
                await update.message.reply_html(
                    "发送失败，你的对话已经被客服删除。请联系客服重新打开对话。"
                )
                return
            reset_user_topic(session, db_user)
        await update.message.reply_html(
            "发送失败，你的对话已经被客服删除。请再发送一条消息用来激活对话。"
        )
    except Exception as exc:
        logger.exception("u2a forward failed")
        await update.message.reply_html(f"发送失败: {exc}\n")
