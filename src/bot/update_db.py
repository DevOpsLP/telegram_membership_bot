import os
import asyncio
import datetime
import logging
import sqlite3
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import ChannelParticipant
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API credentials

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1002143862834"))
SESSION_STRING = os.getenv("SESSION_STRING", "")

# Create Telegram Client
client = TelegramClient(StringSession(SESSION_STRING or None), API_ID, API_HASH)

async def update_database():
    """
    Fetch all users in the channel and calculate how many 30-day periods 
    have elapsed since join_date. Also compute the next due date by adding 
    30-day blocks until it's beyond today. Then, optionally, store these 
    results in the DB or just print them.
    """
    try:
        logger.info("🔄 Connecting to Telegram...")
        await client.connect()

        if not SESSION_STRING:
            logger.info("🔑 Logging in. Enter your phone number when prompted.")
            await client.start()
            new_session_string = client.session.save()
            with open(".env", "r+", encoding="utf-8") as f:
                lines = f.readlines()
                if not any("SESSION_STRING=" in line for line in lines):
                    f.write(f"\nSESSION_STRING={new_session_string}\n")
                    logger.info("✅ Session saved in .env file.")

        logger.info("✅ Client connected!")

        # Get channel entity
        channel = await client.get_entity(CHANNEL_ID)

        # Fetch participants
        logger.info("🔍 Fetching participants...")
        participants = await client.get_participants(channel, limit=300)
        if not participants:
            logger.warning("❌ No participants found.")
            return

        logger.info(f"👥 Total participants: {len(participants)}")

        # Connect to the database
        conn = sqlite3.connect("db/database.db")
        cursor = conn.cursor()

        for participant in participants:
            user_id = participant.id
            username = participant.username or "N/A"
            first_name = participant.first_name or ""
            last_name = participant.last_name or ""
            full_name = f"{first_name} {last_name}".strip() or "N/A"

            # Extract join date
            join_date = None
            if hasattr(participant, "participant") and isinstance(participant.participant, ChannelParticipant):
                if hasattr(participant.participant, "date"):
                    date_value = participant.participant.date
                    if isinstance(date_value, datetime.datetime):
                        join_date = date_value.date()
                    elif isinstance(date_value, int):
                        join_date = datetime.datetime.fromtimestamp(date_value, tz=datetime.timezone.utc).date()

            if not join_date:
                logger.warning(f"⚠️ Skipping {full_name} (ID: {user_id}) - No join date available.")
                continue

            # Calculate how many days since join
            today = datetime.date.today()
            delta_days = (today - join_date).days

            if delta_days < 0:
                # Future join date? Probably an error, skip
                logger.warning(f"❗ {full_name} joined in the future? Skipping.")
                continue

            # Number of complete 30-day blocks
            completed_blocks = delta_days // 30

            # Next due date: keep adding 30-day blocks to join_date until it's after 'today'
            next_due = join_date
            while next_due <= today:
                next_due += datetime.timedelta(days=30)

            # Check what's in the DB (optional)
            cursor.execute("SELECT paid_until FROM users WHERE telegram_user_id = ?", (user_id,))
            existing_record = cursor.fetchone()

            # Just print results (adjust as needed)
            logger.info(
                f"🔎 USER: {full_name} (@{username}), "
                f"Joined: {join_date}, Days since: {delta_days}, "
                f"Blocks: {completed_blocks}, Next due: {next_due}"
            )

            # Optional: store next_due in the DB
            if existing_record:
                current_paid_until = datetime.datetime.strptime(existing_record[0], '%Y-%m-%d').date()
                if current_paid_until < today:
                    # Update with next_due
                    cursor.execute(
                        "UPDATE users SET paid_until = ? WHERE telegram_user_id = ?",
                        (next_due, user_id)
                    )
                    logger.info(f"🆕 Updated paid_until -> {next_due}")
                pass
            else:
                # Insert if doesn't exist
                cursor.execute(
                    "INSERT INTO users (telegram_user_id, username, first_name, last_name, join_date, paid_until) VALUES (?,?,?,?,?,?)",
                    (user_id, username, first_name, last_name, join_date, next_due)
                )
                pass

        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"❌ Error: {e}")
    finally:
        await client.disconnect()
        logger.info("🔌 Disconnected from Telegram.")


if __name__ == "__main__":
    asyncio.run(update_database())