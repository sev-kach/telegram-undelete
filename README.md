# telegram-undelete

Silently saves all your Telegram messages and catches deletions and edits in real time. When someone deletes or edits a message, you get an instant notification through a Telegram bot — with the original text, sender name, @handle, and permanent user ID.

Works for private chats, group chats, and channel direct messages.

## Why this exists

Telegram lets anyone delete messages "for both sides" — permanently erasing what they said from your chat history. There's no built-in way to recover them.

This tool runs quietly in the background, saves every message as it arrives, and alerts you the moment something is deleted or edited. Even if the person changes their username afterwards, you still have their permanent Telegram ID.

## What you get

When someone deletes a message:

```
DELETED
Chat: My Community Chat          ← clickable link to the group
From: John Smith (@john) [ID: 123456789]    ← clickable link to profile
Text: the original message they tried to hide
```

When someone edits a message:

```
EDITED
From: John Smith (@john) [ID: 123456789]
Old: what they originally said
New: what they changed it to
```

- **Private DMs**: shows sender name, @handle, and permanent ID
- **Group chats**: also shows which group, with a clickable link
- **Permanent user ID**: never changes, even if they change their name and username

## How it works

The tool connects to Telegram as your own account (not a bot) using the [Telethon](https://github.com/LonamiWebs/Telethon) library. It receives all messages just like the Telegram app on your phone does. Every message is saved to a local SQLite database. When Telegram sends a "message deleted" or "message edited" event, the tool looks up the original from the database and sends you a notification through a separate Telegram bot.

Your data never leaves your machine (or your server). No third-party services, no cloud storage, no data sharing.

## Quick start

### Prerequisites

- Python 3.8 or higher
- A Telegram account
- A Telegram bot (for notifications)

### 1. Get your Telegram API credentials

1. Go to [my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Click "API development tools"
4. Create an application — you'll get an `api_id` (number) and `api_hash` (string)

These credentials identify your app to Telegram. They don't give anyone access to your account.

### 2. Create a notification bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Save the bot token (looks like `123456789:ABCdefGHI...`)
4. Open a chat with your new bot and send `/start` (required once so the bot can message you)

### 3. Find your Telegram user ID

Message [@userinfobot](https://t.me/userinfobot) on Telegram — it replies with your user ID.

### 4. Set up the project

```bash
git clone https://github.com/sev-kach/telegram-undelete.git
cd telegram-undelete
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your values:

```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your_api_hash_here
BOT_TOKEN=your_bot_token_here
BOT_NOTIFY_USER_ID=your_user_id_here
MONITORED_TYPES=PRIVATE,GROUP
MONITORED_CHATS=
```

### 5. First run (authentication)

```bash
python guard.py
```

On the first run, Telegram will ask for your phone number and send you a verification code. Enter it. If you have two-factor authentication, enter your password too.

This creates a session file locally. You won't need to authenticate again.

### 6. You're done

The guard is running. Send yourself a test message from another account, edit it, then delete it. You should receive notifications from your bot.

Press `Ctrl+C` to stop.

## Configuration

All settings are in the `.env` file:

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_API_ID` | Yes | Your Telegram API ID from my.telegram.org |
| `TELEGRAM_API_HASH` | Yes | Your Telegram API hash |
| `BOT_TOKEN` | Yes | Bot token from @BotFather (for sending you notifications) |
| `BOT_NOTIFY_USER_ID` | Yes | Your Telegram user ID (where notifications are sent) |
| `MONITORED_TYPES` | Yes | Comma-separated chat types: `PRIVATE`, `GROUP`, `CHANNEL` |
| `MONITORED_CHATS` | No | Additional specific chat IDs to monitor (comma-separated) |

### Choosing what to monitor

- `PRIVATE` — all one-on-one DMs (current and future contacts)
- `GROUP` — all small group chats
- `CHANNEL` — all channels and supergroups (can be noisy)
- Specific chat IDs — add individual chats by their numeric ID

To find chat IDs, run:

```bash
python get_chat_ids.py
```

This prints all your chats with their IDs and types.

### Recommended setup

For most users:

```env
MONITORED_TYPES=PRIVATE,GROUP
MONITORED_CHATS=
```

This monitors all private conversations and group chats. New contacts and new groups are automatically included — no config changes needed.

## Running 24/7

The guard only catches messages while it's running. If it's off when a message is sent and deleted, that message is lost. For full coverage, run it on a server that stays on 24/7.

### Option A: Your own computer (simplest)

**Windows**: Edit `start_guard.vbs` with your paths, then copy it to your Startup folder:

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
```

The guard starts silently on every login. No console window.

**Mac/Linux**: Add to your crontab:

```bash
crontab -e
# Add this line:
@reboot cd /path/to/telegram-undelete && python3 guard.py &
```

### Option B: Free cloud server (recommended for 24/7)

You can run this on any server with Python. If you don't have one, Oracle Cloud offers a **free forever** VM that works perfectly:

- 1 CPU, 1 GB RAM (more than enough)
- 30 GB storage
- No credit card charges — truly free

See [docs/ORACLE_CLOUD_SETUP.md](docs/ORACLE_CLOUD_SETUP.md) for a step-by-step guide with screenshots.

After setting up the server:

```bash
# Upload files to your server
scp -r telegram-undelete/ user@your-server:~/

# SSH in
ssh user@your-server

# Install and run
cd telegram-undelete
pip3 install -r requirements.txt
python3 guard.py  # authenticate once

# Set up auto-start (systemd)
sudo tee /etc/systemd/system/telegram-undelete.service > /dev/null << 'EOF'
[Unit]
Description=Telegram Undelete
After=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/telegram-undelete
ExecStart=/usr/bin/python3 guard.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable telegram-undelete
sudo systemctl start telegram-undelete
```

### Option C: Any other server

This runs anywhere with Python 3.8+: DigitalOcean, AWS, Hetzner, a Raspberry Pi, your NAS, or a Docker container. It uses about 40 MB of RAM and negligible CPU.

## Viewing saved messages

### Bot notifications (real-time)

The primary way to see deleted and edited messages. Notifications appear instantly on your phone through the Telegram bot you created.

### HTML report (browsable archive)

The guard generates `deleted_messages.html` — a self-contained page you can open in any browser. It auto-refreshes every 5 minutes and shows:

- All deleted messages with original text
- All edited messages with previous versions
- Stats (total saved, deletions caught, edits caught)

### Command-line viewer

```bash
python view_deleted.py              # show all
python view_deleted.py "chat name"  # filter by chat
```

### Direct database access

All messages are stored in `message_guard.db` (SQLite). You can query it with any SQLite tool:

```sql
-- All deleted messages
SELECT chat_title, sender_name, sender_username, text, deleted_at
FROM messages WHERE deleted = 1 ORDER BY deleted_at DESC;

-- All edits with history
SELECT chat_title, sender_name, text, edit_history
FROM messages WHERE edited = 1;
```

## Privacy and security

- **Your data stays local.** Messages are stored in a SQLite file on your machine or server. Nothing is sent to any external service.
- **The bot only sends TO you.** It doesn't read messages from other users or respond to commands.
- **The session file is sensitive.** `telegram_guard.session` contains your authenticated Telegram session. Treat it like a password — don't share it, don't commit it to git.
- **The `.env` file contains secrets.** API keys and bot tokens. Also never commit this file.
- **The `.gitignore` is pre-configured** to exclude `.env`, session files, databases, and logs.

## Limitations

- Only catches messages that arrive **while the guard is running**. If you start it today, it won't recover messages deleted last week.
- Telegram doesn't always notify clients about deletions in some scenarios. A small number of deletions may be missed.
- Media files (photos, videos) are not saved by default. Only text is preserved.
- The guard creates an additional "session" visible in your Telegram settings under Devices. This is normal — it's your account logged in from Python.

## Files

| File | Purpose | Contains secrets? |
|---|---|---|
| `guard.py` | Main script — monitors and saves messages | No |
| `config.py` | Reads configuration from `.env` | No |
| `get_chat_ids.py` | Utility to list your chats and their IDs | No |
| `view_deleted.py` | Command-line viewer for deleted/edited messages | No |
| `start_guard.vbs` | Windows silent auto-start launcher | No (edit paths) |
| `.env.example` | Template for your configuration | No |
| `.env` | Your actual configuration (not committed) | **Yes** |
| `telegram_guard.session` | Telegram login session (not committed) | **Yes** |
| `message_guard.db` | Local message database (not committed) | Personal data |
| `guard.log` | Activity log (not committed) | Personal data |
| `deleted_messages.html` | HTML report (not committed) | Personal data |

## License

MIT
