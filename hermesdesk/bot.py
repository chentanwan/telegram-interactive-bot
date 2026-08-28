"""Assemble the Telegram application."""

from __future__ import annotations

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    PicklePersistence,
    filters,
)

from hermesdesk.config import ADMIN_GROUP_ID, BOT_TOKEN, PERSISTENCE_PATH
from hermesdesk.db.session import init_db
from hermesdesk.handlers.admin import broadcast, clear, error_handler, forwarding_message_a2u, status
from hermesdesk.handlers.captcha import callback_query_vcode
from hermesdesk.handlers.user import forwarding_message_u2a, start
from hermesdesk.logging_setup import setup_logging


def build_application() -> Application:
    setup_logging()
    init_db()
    PERSISTENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    persistence = PicklePersistence(filepath=str(PERSISTENCE_PATH))
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .persistence(persistence)
        .build()
    )

    application.add_handler(CommandHandler("start", start, filters.ChatType.PRIVATE))
    application.add_handler(
        MessageHandler(~filters.COMMAND & filters.ChatType.PRIVATE, forwarding_message_u2a)
    )
    application.add_handler(
        MessageHandler(~filters.COMMAND & filters.Chat([ADMIN_GROUP_ID]), forwarding_message_a2u)
    )
    application.add_handler(CommandHandler("clear", clear, filters.Chat([ADMIN_GROUP_ID])))
    application.add_handler(
        CommandHandler("broadcast", broadcast, filters.Chat([ADMIN_GROUP_ID]))
    )
    application.add_handler(CommandHandler("status", status, filters.Chat([ADMIN_GROUP_ID])))
    application.add_handler(CallbackQueryHandler(callback_query_vcode, pattern="^vcode_"))
    application.add_error_handler(error_handler)
    return application


def main() -> None:
    application = build_application()
    application.run_polling()
