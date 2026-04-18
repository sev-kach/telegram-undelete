# tools/telegram_guard/view_deleted.py
#
# View all deleted and edited messages from the guard database.
# Run anytime to see what was caught.
#
# Usage:
#   python view_deleted.py              — show all deleted/edited messages
#   python view_deleted.py "chat name"  — filter by chat title

import sqlite3
import sys
from config import DB_PATH


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    chat_filter = sys.argv[1] if len(sys.argv) > 1 else None

    # Deleted messages
    print("=" * 70)
    print("DELETED MESSAGES")
    print("=" * 70)

    query = "SELECT chat_title, sender_name, text, timestamp, deleted_at FROM messages WHERE deleted = 1"
    params = []
    if chat_filter:
        query += " AND chat_title LIKE ?"
        params.append(f"%{chat_filter}%")
    query += " ORDER BY deleted_at DESC"

    c.execute(query, params)
    rows = c.fetchall()

    if not rows:
        print("  (none)")
    for chat, sender, text, ts, del_at in rows:
        print(f"\n  [{chat}] {sender} (sent {ts[:19]})")
        print(f"  Deleted at: {del_at[:19]}")
        print(f"  Text: {text}")

    # Edited messages
    print()
    print("=" * 70)
    print("EDITED MESSAGES")
    print("=" * 70)

    query = "SELECT chat_title, sender_name, text, edit_history, timestamp FROM messages WHERE edited = 1"
    params = []
    if chat_filter:
        query += " AND chat_title LIKE ?"
        params.append(f"%{chat_filter}%")
    query += " ORDER BY timestamp DESC"

    c.execute(query, params)
    rows = c.fetchall()

    if not rows:
        print("  (none)")
    for chat, sender, current_text, history, ts in rows:
        print(f"\n  [{chat}] {sender}")
        print(f"  Current: {current_text[:200]}")
        if history:
            print(f"  Previous versions:")
            for line in history.split("\n"):
                print(f"    {line}")

    # Stats
    print()
    print("=" * 70)
    c.execute("SELECT COUNT(*) FROM messages")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM messages WHERE deleted = 1")
    deleted = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM messages WHERE edited = 1")
    edited = c.fetchone()[0]
    print(f"Total messages saved: {total} | Deleted caught: {deleted} | Edits caught: {edited}")

    conn.close()


if __name__ == "__main__":
    main()
