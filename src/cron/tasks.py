import os
import sys
import asyncio
import datetime
import logging
import sqlite3
import re
from telegram import Bot
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Telegram Bot
bot = Bot(token=BOT_TOKEN)

def escape_markdown_v2(text):
    if not text:
        return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", text)

async def notify_users():
    try:
        today = datetime.date.today()
        tomorrow = today + datetime.timedelta(days=1)

        # Enable safe DATE parsing
        conn = sqlite3.connect("db/database.db", detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT telegram_user_id, first_name, username, paid_until FROM users 
        """)

        expiring_users = cursor.fetchall()

        if not expiring_users:
            logger.info("✅ No users with expiring subscriptions today or tomorrow.")
            return

        for user in expiring_users:
            user_id, first_name, username, paid_until = user

            if user_id != 7498855771:
                continue

            full_name = escape_markdown_v2(first_name or "Usuario")
            if isinstance(paid_until, str):
                paid_until = datetime.datetime.strptime(paid_until, "%Y-%m-%d").date()

            try:
                if paid_until == today:
                    message = (
                        f"⚠️ Hasta el día de hoy llega tu suscripción, de no cancelar, "
                        f"serás automáticamente sacado del grupo\\.\n\n"
                        f"Para renovar contacta a la persona que te ingresó\\.\n\n"
                        f"_Este es un mensaje automático\\._"
                    )
                    await bot.send_message(chat_id=user_id, text=message, parse_mode="MarkdownV2")
                    logger.info(f"✅ Sent today-expiry reminder to {user_id}")

                elif paid_until == tomorrow:
                    message = (
                        f"🔔 Hola {full_name}, mañana se vence tu suscripción, recuerda realizar el pago con anticipación\\.\n\n"
                        "Para renovar contacta a la persona que te agregó al grupo o envia /renovar y un administrador se contactará contigo lo antes posible\\.\n\n"
                        "_Este es un mensaje automático\\._"
                    )
                    await bot.send_message(chat_id=user_id, text=message, parse_mode="MarkdownV2")
                    logger.info(f"✅ Sent tomorrow reminder to {user_id}")

                elif paid_until < today:
                    escaped_date = escape_markdown_v2(str(paid_until))  # Escape date with dashes
                    message = (
                        f"⚠️ Tu suscripción venció el {escaped_date}, y no hemos recibido una renovación\\.\n\n"
                        "Por esta razón serás removido del grupo\\.\n\n"
                        "Para volver a ingresar, realiza el pago correspondiente y usa el comando /start o /renovar\\.\n\n"
                        "_Este es un mensaje automático\\._"
                    )
                    await bot.send_message(chat_id=user_id, text=message, parse_mode="MarkdownV2")
                    logger.info(f"✅ Sent final warning to {user_id}")

                    await bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
                    await bot.unban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
                    logger.info(f"🚪 Kicked user {user_id} from the group")

                    cursor.execute("DELETE FROM users WHERE telegram_user_id = ?", (user_id,))
                    conn.commit()

            except Exception as e:
                logger.error(f"❌ Failed to handle user {user_id}: {e}")
        conn.close()

    except Exception as e:
        logger.error(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(notify_users())