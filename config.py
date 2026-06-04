import os
from dotenv import load_dotenv

# Always load .env from the same directory as this config.py file
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path=_env_path)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8761618853:AAESRAU4EoENxfLa7mRx_pXUmEWEMTj1Q6M")
TELEGRAM_SUPPORT_GROUP_ID = os.getenv("TELEGRAM_SUPPORT_GROUP_ID", "").strip()
TELEGRAM_ADMIN_IDS = [
    int(x.strip()) for x in os.getenv("TELEGRAM_ADMIN_IDS", "").split(",") if x.strip().isdigit()
]

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# List of API keys for rotation
GEMINI_API_KEYS = [k.strip() for k in [GEMINI_API_KEY, GOOGLE_API_KEY] if k.strip()]

# Username configurations
MAIN_BOT_USERNAME = "As2ilabot"
BACKUP_BOT_USERNAME = "minassatalbajibot"

# Academy group — only members of this group can use the bot
ACADEMY_GROUP_ID = int(os.getenv("ACADEMY_GROUP_ID", "-1003724140001"))

# Database paths
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "backup_bot.db")
MAIN_DATABASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../telegram-bot/persistent_storage/academy.db"))
MAIN_CREDENTIALS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../telegram-bot/credentials.json"))
