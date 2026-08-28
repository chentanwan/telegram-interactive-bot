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
from hermesdesk.handlers.admin import (
    ban,
    broadcast,
    clear,
    delete_pair,
    error_handler,
    forwarding_message_a2u,
    info,
    note,
    status,
    unban,
)
from hermesdesk.handlers.captcha import callback_query_vcode
from hermesdesk.handlers.staff import (
    canned_callback,
    claim,
    delreply,
    replies,
    reply_canned,
    setreply,
    unclaim,
)
from hermesdesk.handlers.sync import edited_message_a2u, edited_message_u2a
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
        MessageHandler(
            filters.UpdateType.EDITED_MESSAGE & filters.ChatType.PRIVATE,
            edited_message_u2a,
        )
    )
    application.add_handler(
        MessageHandler(
            ~filters.COMMAND
            & ~filters.UpdateType.EDITED_MESSAGE
            & filters.ChatType.PRIVATE,
            forwarding_message_u2a,
        )
    )
    admin_chat = filters.Chat([ADMIN_GROUP_ID])
    application.add_handler(
        MessageHandler(filters.UpdateType.EDITED_MESSAGE & admin_chat, edited_message_a2u)
    )
    application.add_handler(
        MessageHandler(
            ~filters.COMMAND & ~filters.UpdateType.EDITED_MESSAGE & admin_chat,
            forwarding_message_a2u,
        )
    )
    application.add_handler(CommandHandler("clear", clear, admin_chat))
    application.add_handler(CommandHandler("broadcast", broadcast, admin_chat))
    application.add_handler(CommandHandler("status", status, admin_chat))
    application.add_handler(CommandHandler("ban", ban, admin_chat))
    application.add_handler(CommandHandler("unban", unban, admin_chat))
    application.add_handler(CommandHandler("info", info, admin_chat))
    application.add_handler(CommandHandler("note", note, admin_chat))
    application.add_handler(CommandHandler("del", delete_pair, admin_chat))
    application.add_handler(CommandHandler("claim", claim, admin_chat))
    application.add_handler(CommandHandler("unclaim", unclaim, admin_chat))
    application.add_handler(CommandHandler("replies", replies, admin_chat))
    application.add_handler(CommandHandler("setreply", setreply, admin_chat))
    application.add_handler(CommandHandler("delreply", delreply, admin_chat))
    application.add_handler(CommandHandler("reply", reply_canned, admin_chat))
    application.add_handler(CallbackQueryHandler(canned_callback, pattern="^canned_"))
    application.add_handler(CallbackQueryHandler(callback_query_vcode, pattern="^vcode_"))
    application.add_error_handler(error_handler)
    return application


def main() -> None:
    application = build_application()
    application.run_polling()
