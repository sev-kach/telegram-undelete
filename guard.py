# tools/telegram_guard/guard.py
#
# Telegram Message Guard — silently saves messages from monitored chats
# and preserves them when someone deletes or edits a message.
#
# All data stored locally in SQLite. Nothing leaves your machine.
#
# Usage:
#   1. Fill in config.py (API credentials + chat list)
#   2. Run: python guard.py
#   3. First run: enter your phone number + code to authenticate
#   4. Leave running in background. Ctrl+C to stop.

import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timezone

from telethon import TelegramClient, events

# File-based logging (since pythonw has no console)
logging.basicConfig(
    filename="guard.log",
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("guard")
from config import (
    API_ID, API_HASH, SESSION_NAME, DB_PATH,
    MONITORED_TYPES, MONITORED_CHATS, LOG_DELETED, LOG_EDITED,
    BOT_TOKEN, BOT_NOTIFY_USER_ID,
)

import urllib.request
import urllib.parse
import json as _json


def send_bot_alert(text: str):
    """Send a notification via Telegram bot. Non-blocking, failures are logged and ignored."""
    if not BOT_TOKEN or not BOT_NOTIFY_USER_ID:
        return
    try:
        # Truncate to Telegram's 4096 char limit
        if len(text) > 4000:
            text = text[:4000] + "\n... (truncated)"
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": BOT_NOTIFY_USER_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log.warning(f"Bot alert failed: {e}")


def init_db():
    """Create the local SQLite database for message storage."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER,
            chat_id INTEGER,
            chat_title TEXT,
            sender_id INTEGER,
            sender_name TEXT,
            sender_username TEXT,
            text TEXT,
            timestamp TEXT,
            deleted INTEGER DEFAULT 0,
            deleted_at TEXT,
            edited INTEGER DEFAULT 0,
            edit_history TEXT,
            PRIMARY KEY (id, chat_id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS events_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            chat_id INTEGER,
            chat_title TEXT,
            message_id INTEGER,
            sender_name TEXT,
            original_text TEXT,
            new_text TEXT,
            event_at TEXT
        )
    """)
    conn.commit()
    return conn


# Extra chat IDs to always monitor (from config)
_extra_chat_ids = set()
# Chat type cache: chat_id → type string
_chat_type_cache = {}
# Own account + notification-bot user IDs (set in main() once the client is logged in).
# Used to suppress self-notification loops: skip saving the bot's own alert messages,
# and skip sending a new alert when the original sender was you or the bot itself.
_my_user_id = 0
_bot_user_id = 0


async def resolve_monitored_chats(client):
    """Build the chat type cache and resolve extra chat IDs."""
    if not MONITORED_TYPES and not MONITORED_CHATS:
        print("WARNING: Nothing to monitor. Set MONITORED_TYPES or MONITORED_CHATS in config.py.")
        return

    # Cache chat types from existing dialogs
    async for dialog in client.iter_dialogs():
        if dialog.is_channel:
            _chat_type_cache[dialog.id] = "CHANNEL"
        elif dialog.is_group:
            _chat_type_cache[dialog.id] = "GROUP"
        else:
            _chat_type_cache[dialog.id] = "PRIVATE"

    # Resolve extra chat IDs
    for item in MONITORED_CHATS:
        if isinstance(item, int):
            _extra_chat_ids.add(item)

    type_str = ", ".join(MONITORED_TYPES) if MONITORED_TYPES else "(none)"
    extra_str = f" + {len(_extra_chat_ids)} specific chats" if _extra_chat_ids else ""
    print(f"Monitoring types: [{type_str}]{extra_str}")
    print(f"  PRIVATE chats in cache: {sum(1 for t in _chat_type_cache.values() if t == 'PRIVATE')}")
    print(f"  GROUP chats in cache: {sum(1 for t in _chat_type_cache.values() if t == 'GROUP')}")
    print(f"  CHANNEL chats in cache: {sum(1 for t in _chat_type_cache.values() if t == 'CHANNEL')}")


def is_monitored(chat_id: int, event=None) -> bool:
    """Check if a chat should be monitored based on type filters + extra IDs."""
    # Always include explicitly listed chats
    if chat_id in _extra_chat_ids:
        return True

    # Check type filter
    chat_type = _chat_type_cache.get(chat_id)

    # For new chats not in cache yet, determine type from the event
    if chat_type is None and event and hasattr(event, 'chat'):
        chat = event.chat
        if chat:
            if hasattr(chat, 'megagroup') and chat.megagroup:
                chat_type = "CHANNEL"
            elif hasattr(chat, 'broadcast') and chat.broadcast:
                chat_type = "CHANNEL"
            elif hasattr(chat, 'gigagroup') and chat.gigagroup:
                chat_type = "CHANNEL"
            elif hasattr(chat, 'title'):
                chat_type = "GROUP"
            else:
                chat_type = "PRIVATE"
            _chat_type_cache[chat_id] = chat_type

    # Fallback: if still unknown, treat as PRIVATE (safer to save than miss)
    if chat_type is None:
        chat_type = "PRIVATE"
        _chat_type_cache[chat_id] = chat_type

    return chat_type in MONITORED_TYPES


def save_message(conn, msg, chat_title: str, sender=None):
    """Save or update a message in the local database."""
    sender_name = ""
    sender_username = ""
    # Use explicitly passed sender (pre-fetched), fall back to msg.sender
    s = sender or msg.sender
    if s:
        if hasattr(s, 'first_name'):
            sender_name = f"{s.first_name or ''} {s.last_name or ''}".strip()
        elif hasattr(s, 'title'):
            sender_name = s.title or ""
        if hasattr(s, 'username') and s.username:
            sender_username = s.username

    text = msg.text or msg.message or ""
    timestamp = msg.date.isoformat() if msg.date else datetime.now(timezone.utc).isoformat()

    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO messages (id, chat_id, chat_title, sender_id, sender_name, sender_username, text, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (msg.id, msg.chat_id, chat_title, msg.sender_id, sender_name, sender_username, text, timestamp))
    conn.commit()


def _format_from(sender_name: str, sender_username: str, sender_id: int = 0) -> str:
    """Format the sender with @handle link and permanent ID."""
    name = sender_name or "Unknown"
    parts = []
    if sender_username:
        parts.append(f'<a href="https://t.me/{sender_username}">{name}</a> (@{sender_username})')
    elif sender_id:
        parts.append(f'<a href="tg://user?id={sender_id}">{name}</a>')
    else:
        parts.append(name)
    if sender_id:
        parts.append(f"[ID: {sender_id}]")
    return " ".join(parts)


def _format_alert(event_type: str, chat_title: str, chat_id: int,
                  sender_name: str, sender_username: str, text: str,
                  sender_id: int = 0,
                  old_text: str = None, is_private: bool = False) -> str:
    """Format a bot notification message."""
    from_str = _format_from(sender_name, sender_username, sender_id)

    parts = [f"<b>{event_type}</b>"]

    if not is_private and chat_title:
        # Supergroups/channels have negative IDs starting with -100
        chat_id_str = str(abs(chat_id)) if chat_id else ""
        if chat_id_str.startswith("100"):
            # Remove the "100" prefix to get the actual Telegram chat ID for links
            link_id = chat_id_str[3:]
            parts.append(f'<b>Chat:</b> <a href="https://t.me/c/{link_id}/1">{chat_title}</a>')
        else:
            parts.append(f"<b>Chat:</b> {chat_title}")

    parts.append(f"<b>From:</b> {from_str}")

    if event_type == "EDITED" and old_text is not None:
        parts.append(f"<b>Old:</b> {old_text}")
        parts.append(f"<b>New:</b> {text}")
    else:
        parts.append(f"<b>Text:</b> {text or '(empty)'}")

    return "\n".join(parts)


async def _text_or_refetch(client, msg, chat_id):
    """Return (msg_to_save, text) or (None, '') if nothing recoverable.

    When Telethon catches up after an MTProto sync failure, getDifference can
    return Message stubs with an empty text field. Saving those produces
    useless '(empty)' deletion notifications later. If the incoming object has
    no text, we re-fetch the message from the server; if even that comes back
    empty (media-only, TTL/view-once, or truly gone), we signal 'do not save'
    so no empty row is ever written.
    """
    text = msg.text or msg.message or ""
    if text:
        return msg, text
    try:
        fresh = await client.get_messages(chat_id, ids=[msg.id])
    except Exception as e:
        log.warning(f"text re-fetch failed for msg {msg.id} in {chat_id}: {e}")
        return None, ""
    if not fresh:
        return None, ""
    fm = fresh[0] if isinstance(fresh, list) else fresh
    if not fm:
        return None, ""
    text = fm.text or fm.message or ""
    if not text:
        return None, ""
    return fm, text


def mark_deleted(conn, chat_id: int, message_ids: list):
    """Mark messages as deleted, preserving the original text."""
    now = datetime.now(timezone.utc).isoformat()
    c = conn.cursor()
    for msg_id in message_ids:
        if chat_id and chat_id != 0:
            c.execute("""
                UPDATE messages SET deleted = 1, deleted_at = ? WHERE id = ? AND chat_id = ?
            """, (now, msg_id, chat_id))
            c.execute("SELECT sender_name, text, chat_title, sender_id, chat_id, sender_username FROM messages WHERE id = ? AND chat_id = ?",
                      (msg_id, chat_id))
        else:
            # Private message deletions often have chat_id=0 — search by message ID only
            c.execute("""
                UPDATE messages SET deleted = 1, deleted_at = ? WHERE id = ?
            """, (now, msg_id))
            c.execute("SELECT sender_name, text, chat_title, sender_id, chat_id, sender_username FROM messages WHERE id = ?",
                      (msg_id,))
        row = c.fetchone()
        if row:
            sender_name, text, chat_title, sender_id, actual_chat_id, sender_username = row
            c.execute("""
                INSERT INTO events_log (event_type, chat_id, chat_title, message_id, sender_name, original_text, event_at)
                VALUES ('deleted', ?, ?, ?, ?, ?, ?)
            """, (actual_chat_id or chat_id, chat_title, msg_id, sender_name, text, now))
            print(f"  DELETED: [{chat_title}] {sender_name}: {(text or '')[:100]}...")

            # Skip notification when the original sender was you or the notification
            # bot itself — but keep the DB row so the HTML report stays accurate.
            skip_notify = bool(sender_id) and (
                sender_id == _my_user_id or sender_id == _bot_user_id
            )
            if not skip_notify:
                # Private chats: sender_id == chat_id (positive number)
                is_private = (actual_chat_id or 0) > 0
                send_bot_alert(_format_alert(
                    "DELETED", chat_title, actual_chat_id or chat_id,
                    sender_name, sender_username or "", text,
                    sender_id=sender_id or 0, is_private=is_private,
                ))

    conn.commit()


def log_edit(conn, msg, chat_title: str, old_text: str):
    """Log an edit event, preserving both old and new text."""
    now = datetime.now(timezone.utc).isoformat()
    new_text = msg.text or msg.message or ""
    sender_name = ""
    if msg.sender:
        if hasattr(msg.sender, 'first_name'):
            sender_name = f"{msg.sender.first_name or ''} {msg.sender.last_name or ''}".strip()

    c = conn.cursor()
    # Append to edit history
    c.execute("SELECT edit_history FROM messages WHERE id = ? AND chat_id = ?", (msg.id, msg.chat_id))
    row = c.fetchone()
    history = row[0] if row and row[0] else ""
    history += f"\n[{now}] {old_text}" if history else f"[{now}] {old_text}"

    c.execute("""
        UPDATE messages SET text = ?, edited = 1, edit_history = ? WHERE id = ? AND chat_id = ?
    """, (new_text, history, msg.id, msg.chat_id))

    c.execute("""
        INSERT INTO events_log (event_type, chat_id, chat_title, message_id, sender_name, original_text, new_text, event_at)
        VALUES ('edited', ?, ?, ?, ?, ?, ?, ?)
    """, (msg.chat_id, chat_title, msg.id, sender_name, old_text, new_text, now))

    conn.commit()
    print(f"  EDITED: [{chat_title}] {sender_name}: '{old_text[:60]}' → '{new_text[:60]}'")

    sender_username = ""
    if msg.sender and hasattr(msg.sender, 'username') and msg.sender.username:
        sender_username = msg.sender.username

    skip_notify = bool(msg.sender_id) and (
        msg.sender_id == _my_user_id or msg.sender_id == _bot_user_id
    )
    if not skip_notify:
        is_private = (msg.chat_id or 0) > 0
        send_bot_alert(_format_alert(
            "EDITED", chat_title, msg.chat_id,
            sender_name, sender_username, new_text,
            sender_id=msg.sender_id or 0,
            old_text=old_text, is_private=is_private,
        ))


def generate_html_report(conn):
    """Generate a self-contained HTML file showing deleted and edited messages."""
    c = conn.cursor()

    # Deleted messages (include edit history if message was edited before deletion)
    c.execute("""
        SELECT chat_title, sender_name, text, timestamp, deleted_at, edit_history
        FROM messages WHERE deleted = 1 ORDER BY deleted_at DESC
    """)
    deleted = c.fetchall()

    # Edited messages
    c.execute("""
        SELECT chat_title, sender_name, text, edit_history, timestamp
        FROM messages WHERE edited = 1 ORDER BY timestamp DESC
    """)
    edited = c.fetchall()

    # Stats
    c.execute("SELECT COUNT(*) FROM messages")
    total = c.fetchone()[0]

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Telegram Guard — Deleted &amp; Edited Messages</title>
<meta http-equiv="refresh" content="300">
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #e0e0e0; margin: 0; padding: 20px; }}
    h1 {{ color: #00d4ff; border-bottom: 2px solid #00d4ff; padding-bottom: 10px; }}
    h2 {{ color: #ff6b6b; margin-top: 30px; }}
    .stats {{ background: #16213e; padding: 15px; border-radius: 8px; margin: 15px 0; display: flex; gap: 30px; }}
    .stat {{ text-align: center; }}
    .stat-num {{ font-size: 28px; font-weight: bold; color: #00d4ff; }}
    .stat-label {{ font-size: 12px; color: #888; text-transform: uppercase; }}
    .msg {{ background: #16213e; border-left: 4px solid #ff6b6b; padding: 12px 16px; margin: 10px 0; border-radius: 0 8px 8px 0; }}
    .msg.edit {{ border-left-color: #ffa500; }}
    .msg-header {{ display: flex; justify-content: space-between; margin-bottom: 6px; }}
    .msg-chat {{ color: #00d4ff; font-weight: 600; }}
    .msg-sender {{ color: #a8e6cf; }}
    .msg-time {{ color: #666; font-size: 12px; }}
    .msg-text {{ white-space: pre-wrap; word-wrap: break-word; line-height: 1.5; }}
    .msg-deleted-at {{ color: #ff6b6b; font-size: 12px; margin-top: 6px; }}
    .msg-old {{ color: #888; font-size: 13px; margin-top: 6px; padding: 6px; background: #0f0f23; border-radius: 4px; }}
    .empty {{ color: #555; font-style: italic; padding: 20px; }}
    .updated {{ color: #444; font-size: 11px; text-align: right; margin-top: 20px; }}
</style>
</head>
<body>
<h1>Telegram Guard</h1>
<div class="stats">
    <div class="stat"><div class="stat-num">{total}</div><div class="stat-label">Messages Saved</div></div>
    <div class="stat"><div class="stat-num">{len(deleted)}</div><div class="stat-label">Deleted Caught</div></div>
    <div class="stat"><div class="stat-num">{len(edited)}</div><div class="stat-label">Edits Caught</div></div>
</div>

<h2>Deleted Messages</h2>
"""

    if not deleted:
        html += '<div class="empty">No deleted messages caught yet.</div>\n'
    for chat, sender, text, ts, del_at, edit_history in deleted:
        text_safe = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        history_html = ""
        if edit_history:
            history_safe = edit_history.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            history_html = f'\n    <div class="msg-old">Previous versions:\n{history_safe}</div>'
        html += f"""<div class="msg">
    <div class="msg-header">
        <span><span class="msg-chat">{chat or "?"}</span> &mdash; <span class="msg-sender">{sender or "?"}</span></span>
        <span class="msg-time">{(ts or "")[:19]}</span>
    </div>
    <div class="msg-text">{text_safe}</div>{history_html}
    <div class="msg-deleted-at">Deleted at {(del_at or "")[:19]}</div>
</div>
"""

    html += "<h2>Edited Messages</h2>\n"

    if not edited:
        html += '<div class="empty">No edited messages caught yet.</div>\n'
    for chat, sender, current, history, ts in edited:
        current_safe = (current or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        history_safe = (history or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html += f"""<div class="msg edit">
    <div class="msg-header">
        <span><span class="msg-chat">{chat or "?"}</span> &mdash; <span class="msg-sender">{sender or "?"}</span></span>
        <span class="msg-time">{(ts or "")[:19]}</span>
    </div>
    <div class="msg-text">{current_safe}</div>
    <div class="msg-old">Previous: {history_safe}</div>
</div>
"""

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    html += f'<div class="updated">Last updated: {now} &mdash; auto-refreshes every 5 minutes</div>\n'
    html += "</body>\n</html>"

    report_path = "deleted_messages.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)


async def main():
    print("Telegram Message Guard starting...")
    print()

    if not API_ID or not API_HASH:
        print("ERROR: Set API_ID and API_HASH in config.py first.")
        print("Get them from https://my.telegram.org")
        return

    conn = init_db()
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()

    me = await client.get_me()
    print(f"Logged in as: {me.first_name} ({me.phone})")

    global _my_user_id, _bot_user_id
    _my_user_id = me.id
    if BOT_TOKEN and ":" in BOT_TOKEN:
        try:
            _bot_user_id = int(BOT_TOKEN.split(":", 1)[0])
        except ValueError:
            _bot_user_id = 0
    print(f"Self-notify filter: my_id={_my_user_id}, bot_id={_bot_user_id}")
    print()

    await resolve_monitored_chats(client)
    print()

    # Cache chat titles
    chat_titles = {}
    async for dialog in client.iter_dialogs():
        chat_titles[dialog.id] = dialog.title or dialog.name or str(dialog.id)

    # ─── Event: New message ───
    @client.on(events.NewMessage(incoming=True))
    async def on_new_message(event):
        if not is_monitored(event.chat_id, event):
            return
        # Ignore the notification bot's own alert messages — otherwise deletions of
        # those alerts would trigger new alerts in a feedback loop.
        if _bot_user_id and event.message.sender_id == _bot_user_id:
            return
        msg, text = await _text_or_refetch(client, event.message, event.chat_id)
        if msg is None:
            log.info(f"SKIP SAVE (no recoverable text): id={event.message.id} chat={event.chat_id}")
            return
        sender = await event.get_sender()
        title = chat_titles.get(event.chat_id, str(event.chat_id))
        save_message(conn, msg, title, sender=sender)
        log.info(f"SAVED: [{title}] {msg.sender_id}: {text[:80]}")

    # Also catch outgoing messages (your own)
    @client.on(events.NewMessage(outgoing=True))
    async def on_own_message(event):
        if not is_monitored(event.chat_id, event):
            return
        msg, text = await _text_or_refetch(client, event.message, event.chat_id)
        if msg is None:
            log.info(f"SKIP SAVE own (no recoverable text): id={event.message.id} chat={event.chat_id}")
            return
        sender = await event.get_sender()
        title = chat_titles.get(event.chat_id, str(event.chat_id))
        save_message(conn, msg, title, sender=sender)
        log.info(f"SAVED (own): [{title}] {text[:80]}")

    # ─── Event: Message deleted ───
    if LOG_DELETED:
        @client.on(events.MessageDeleted())
        async def on_message_deleted(event):
            chat_id = event.chat_id or 0
            log.info(f"DELETE event: chat_id={chat_id}, ids={event.deleted_ids}")
            if chat_id and not is_monitored(chat_id):
                log.info(f"DELETE skipped: chat {chat_id} not monitored")
                return
            mark_deleted(conn, chat_id, event.deleted_ids)
            generate_html_report(conn)

    # ─── Event: Message edited ───
    if LOG_EDITED:
        @client.on(events.MessageEdited())
        async def on_message_edited(event):
            log.info(f"EDIT event: chat_id={event.chat_id}, msg_id={event.message.id}")
            if not is_monitored(event.chat_id, event):
                log.info(f"EDIT skipped: chat {event.chat_id} not monitored")
                return
            title = chat_titles.get(event.chat_id, str(event.chat_id))
            # Get old text from DB
            c = conn.cursor()
            c.execute("SELECT text FROM messages WHERE id = ? AND chat_id = ?",
                      (event.message.id, event.chat_id))
            row = c.fetchone()
            old_text = row[0] if row else "(unknown — message was sent before guard started)"
            log_edit(conn, event.message, title, old_text)
            # Don't call save_message here — log_edit already updates the text.
            # save_message does INSERT OR REPLACE which wipes edit_history.
            generate_html_report(conn)

    # Generate the HTML report on startup
    generate_html_report(conn)

    # Auto-refresh the HTML report every 5 minutes
    async def periodic_html_refresh():
        while True:
            await asyncio.sleep(300)
            generate_html_report(conn)

    asyncio.get_event_loop().create_task(periodic_html_refresh())

    print("Guard is running. Monitoring messages...")
    print(f"HTML report: {os.path.abspath('deleted_messages.html')}")
    print("Press Ctrl+C to stop.")
    print()

    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGuard stopped.")
