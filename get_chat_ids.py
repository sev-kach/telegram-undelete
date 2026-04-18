# tools/telegram_guard/get_chat_ids.py
#
# Utility: lists all your Telegram chats with their IDs.
# Run this once to find the chat IDs you want to monitor,
# then add them to config.py MONITORED_CHATS.

import asyncio
from telethon import TelegramClient
from config import API_ID, API_HASH, SESSION_NAME


async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()

    print(f"{'Type':<12} {'Chat ID':<20} {'Title / Name'}")
    print("-" * 70)

    async for dialog in client.iter_dialogs():
        chat_type = "Channel" if dialog.is_channel else "Group" if dialog.is_group else "User"
        title = dialog.title or dialog.name or "?"
        print(f"{chat_type:<12} {dialog.id:<20} {title}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
