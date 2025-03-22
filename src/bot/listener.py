import datetime
import logging
from telegram import Update
from telegram.ext import MessageHandler, CallbackContext, filters
from db.database import create_connection
from config.config import DATABASE_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def register_new_user(update: Update, context: CallbackContext) -> None:
    """Handles new users joining the group and registers them in the database."""
    for member in update.message.new_chat_members:
        telegram_user_id = member.id
        first_name = member.first_name or ""
        last_name = member.last_name or ""
        username = member.username or ""

        conn = create_connection(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT id, paid_until FROM users WHERE telegram_user_id = ?", (telegram_user_id,))
        existing_user = cursor.fetchone()

        if not existing_user:
            join_date = datetime.datetime.now().strftime('%Y-%m-%d')
            paid_until = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime('%Y-%m-%d')

            cursor.execute("""
                INSERT INTO users (telegram_user_id, username, first_name, last_name, join_date, paid_until, last_payment_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (telegram_user_id, username, first_name, last_name, join_date, paid_until, join_date))
            
            conn.commit()
            logger.info(f"✅ New user registered: {first_name} (@{username}), access valid until {paid_until}")
        else:
            paid_until = datetime.datetime.strptime(existing_user[1], '%Y-%m-%d')
            if datetime.datetime.now() > paid_until:
                update.message.reply_text("🚫 Tu acceso ha expirado. Contacta con un administrador para renovarlo.")
                context.bot.ban_chat_member(chat_id=update.message.chat.id, user_id=telegram_user_id)
                context.bot.unban_chat_member(chat_id=update.message.chat.id, user_id=telegram_user_id)            
                cursor.execute("DELETE FROM users WHERE telegram_user_id = ?", (telegram_user_id,))

                cursor.execute("DELETE FROM users WHERE telegram_user_id = ?", (telegram_user_id,))
                conn.commit()
                logger.info(f"🚨 User {first_name} (@{username}) was kicked for overdue payment.")

        conn.close()

def get_listeners():
    """Return event handlers for integration in main.py"""
    return [MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, register_new_user)]