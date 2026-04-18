# tools/telegram_guard/config.py
#
# Reads all configuration from .env file.
# Copy .env.example to .env and fill in your values.
# Never commit .env to version control.

import os

# Load .env file manually (no external dependency needed)
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

# ─── Telegram API credentials ───
API_ID = int(os.environ.get("TELEGRAM_API_ID", "0"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")

# ─── Session & Database ───
SESSION_NAME = "telegram_guard"
DB_PATH = "message_guard.db"

# ─── Bot Notifications ───
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
BOT_NOTIFY_USER_ID = int(os.environ.get("BOT_NOTIFY_USER_ID", "0"))

# ─── Monitoring Filters ───
_types_raw = os.environ.get("MONITORED_TYPES", "")
MONITORED_TYPES = [t.strip() for t in _types_raw.split(",") if t.strip()]

_chats_raw = os.environ.get("MONITORED_CHATS", "")
MONITORED_CHATS = [int(c.strip()) for c in _chats_raw.split(",") if c.strip()]

# ─── Logging ───
LOG_DELETED = True
LOG_EDITED = True
SAVE_MEDIA = False
