# config/config.py

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Fetch values from .env
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
ADMIN_IDS = os.getenv("ADMIN_IDS", "")  # Comma-separated list of admin IDs
SESSION_NAME = os.getenv("SESSION_NAME", "bot_session")

# Convert ADMIN_IDS from comma-separated string to a set of integers
ADMIN_IDS = set(map(int, ADMIN_IDS.split(','))) if ADMIN_IDS else set()

# Path to SQLite database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "../db/database.db")