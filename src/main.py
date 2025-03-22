# main.py

from telegram.ext import ApplicationBuilder
from bot.commands import get_handlers
from bot.listener import get_listeners
from config.config import BOT_TOKEN
from db.database import init_db  # ✅ Import database initialization

def main():
    # ✅ Initialize the database before starting the bot
    init_db()

    # Create Application instead of Updater
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add command handlers
    for handler in get_handlers():
        app.add_handler(handler)

    # # Add listener handlers
    # for listener in get_listeners():
    #     app.add_handler(listener)

    # Start the bot
    app.run_polling()

if __name__ == "__main__":
    main()