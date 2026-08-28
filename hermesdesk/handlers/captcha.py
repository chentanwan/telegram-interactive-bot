"""Lightweight image captcha for first contact."""

from __future__ import annotations

import os
import random
import time
from string import ascii_letters as letters

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from telegram.helpers import mention_html

from hermesdesk.config import CAPTCHA_DIR
from hermesdesk.services.jobs import delete_message_later


async def ensure_human(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.user_data.get("is_human", False):
        return True
    if context.user_data.get("is_human_error_time", 0) > time.time() - 120:
        await update.message.reply_html("你已经被禁言，请稍后再尝试。")
        return False

    if not CAPTCHA_DIR.exists():
        context.user_data["is_human"] = True
        return True

    files = [name for name in os.listdir(CAPTCHA_DIR) if name.endswith(".png")]
    if not files:
        context.user_data["is_human"] = True
        return True

    file_name = random.choice(files)
    code = file_name.replace("image_", "").replace(".png", "")
    file_path = CAPTCHA_DIR / file_name
    codes = ["".join(random.sample(letters, 5)) for _ in range(7)]
    codes.append(code)
    random.shuffle(codes)

    photo = context.bot_data.get(f"image|{code}") or str(file_path)
    user = update.effective_user
    buttons = [
        InlineKeyboardButton(text, callback_data=f"vcode_{text}_{user.id}")
        for text in codes
    ]
    button_matrix = [buttons[i : i + 4] for i in range(0, len(buttons), 4)]
    sent = await update.message.reply_photo(
        photo,
        f"{mention_html(user.id, user.first_name)}请选择图片中的文字。回答错误将无法联系客服。",
        reply_markup=InlineKeyboardMarkup(button_matrix),
        parse_mode="HTML",
    )
    biggest_photo = sorted(sent.photo, key=lambda item: item.file_size, reverse=True)[0]
    context.bot_data[f"image|{code}"] = biggest_photo.file_id
    context.user_data["vcode"] = code
    await delete_message_later(60, sent.chat.id, sent.message_id, context)
    return False


async def callback_query_vcode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    _, code, user_id = query.data.split("_", 2)
    if user_id == str(user.id):
        if code == context.user_data.get("vcode"):
            await query.answer("正确，欢迎。")
            await context.bot.send_message(
                update.effective_chat.id,
                f"{mention_html(user.id, user.first_name)} , 欢迎。",
                parse_mode="HTML",
            )
            context.user_data["is_human"] = True
        else:
            await query.answer("~错误~，禁言2分钟")
            context.user_data["is_human_error_time"] = time.time()
    await query.message.delete()
