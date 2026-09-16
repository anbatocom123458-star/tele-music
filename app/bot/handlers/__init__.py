"""Handler registration — single source of routing truth."""
from __future__ import annotations

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.bot.handlers import (
    account,
    admin,
    dispatch,
    history,
    menu,
    new_chat,
    redeem,
    start,
    svg,
    voice,
)


def register_handlers(app: Application) -> None:
    # Commands (group 0)
    app.add_handler(CommandHandler("start", start.start), group=0)
    app.add_handler(CommandHandler("help", start.help_cmd), group=0)
    app.add_handler(CommandHandler("redeem", redeem.redeem), group=0)
    app.add_handler(CommandHandler("acc", account.acc), group=0)
    app.add_handler(CommandHandler("new", new_chat.new_chat), group=0)
    app.add_handler(CommandHandler("voice", voice.voice_command), group=0)
    app.add_handler(CommandHandler("svg", svg.svg_command), group=0)
    app.add_handler(CommandHandler("history", history.history), group=0)
    app.add_handler(CommandHandler("admin", admin.admin), group=0)
    app.add_handler(CommandHandler("addcredit", admin.addcredit), group=0)

    # Inline keyboard callbacks (group 0, distinct prefixes)
    app.add_handler(CallbackQueryHandler(voice.handle_voice_callback_entry, pattern=r"^voice:"), group=0)
    app.add_handler(CallbackQueryHandler(svg.handle_svg_action_entry, pattern=r"^svgaction:"), group=0)
    app.add_handler(CallbackQueryHandler(history.handle_conv_callback_entry, pattern=r"^conv:"), group=0)
    app.add_handler(CallbackQueryHandler(menu.handle_menu_entry, pattern=r"^menu:"), group=0)
    app.add_handler(CallbackQueryHandler(menu.handle_cancel_entry, pattern=r"^cancel:"), group=0)

    # Plain text routed by persisted state (group 1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, dispatch.route_text), group=1)

