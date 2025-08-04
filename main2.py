#!/usr/bin/env python3
# coding: utf-8

import re, asyncio, datetime, mimetypes
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from io import BytesIO
from config import API_ID, API_HASH, BOT_TOKEN, USER_SESSION, TARGET_CHAT_ID



# ── Учетные данные (заполнить своими) ─────────────────────────────────────────────
API_ID        = 123456
API_HASH      = "your_api_hash_here"
BOT_TOKEN     = "your_bot_token_here"
USER_SESSION  = "your_user_session_here"

if not (API_ID and API_HASH and BOT_TOKEN):
    raise RuntimeError("Заполни API_ID, API_HASH, BOT_TOKEN")

DESKTOP_KWARGS = dict(
    device_model="Custom Device",
    system_version="Custom OS",
    app_version="1.0",
    lang_code="en",
    system_lang_code="en"
)

user_client = TelegramClient(
    StringSession(USER_SESSION), API_ID, API_HASH, **DESKTOP_KWARGS
)
bot_client = TelegramClient("my_bot_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# ← Укажи ID Telegram-группы
TARGET_CHAT_ID = -1001234567890

# Регулярки
URL_RE   = re.compile(r"https?://\S+")
HASH_RE  = re.compile(r"#\w+")

# Индивидуальные форматтеры
def format_koltrack(text):
    return "\n".join(
        line for line in text.splitlines()
        if not ("Search on X" in line and "Join Discord" in line)
    )

def format_rugpull(text):
    return HASH_RE.sub("", URL_RE.sub("", text)).strip()


def log(text):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {text}")


async def ensure_authorized():
    if USER_SESSION:
        return
    log("Нет строковой сессии — авторизуюсь вручную…")
    await user_client.start(
        phone=lambda: input("Введите номер телефона: "),
        password=lambda: input("Пароль 2FA (если включён): ")
    )
    session_str = user_client.session.save()
    log("\nСессия создана! Сохрани это:")
    print(f"USER_SESSION = '{session_str}'")
    raise SystemExit


async def process_new_messages(src, topic_id, formatter):
    last_checked = datetime.datetime.now(datetime.timezone.utc)

    while True:
        published = 0
        try:
            msgs = await user_client.get_messages(src, limit=20)
            for m in reversed(msgs):
                if m.date <= last_checked:
                    continue
                last_checked = max(last_checked, m.date)
                text = formatter(m.text or "")
                if "wallet" not in text.lower():
                    continue

                if m.media:
                    is_photo = False
                    file_name = "media"
                    mime_type = None

                    if hasattr(m.media, 'photo'):
                        is_photo = True
                        file_name = "image.jpg"
                        mime_type = "image/jpeg"
                    elif hasattr(m.media, 'document'):
                        doc = m.media.document
                        if hasattr(doc, 'attributes'):
                            for attr in doc.attributes:
                                if hasattr(attr, 'file_name') and attr.file_name:
                                    file_name = attr.file_name
                                    mime_type = mimetypes.guess_type(file_name)[0]
                                    break
                        if hasattr(doc, 'mime_type') and doc.mime_type:
                            mime_type = doc.mime_type
                            if mime_type.startswith('image/'):
                                is_photo = True
                                if file_name == "media":
                                    ext = mime_type.split('/')[1]
                                    file_name = f"image.{ext}"

                    data = await user_client.download_media(m, file=bytes)
                    buf = BytesIO(data)
                    buf.name = file_name

                    await bot_client.send_file(
                        TARGET_CHAT_ID,
                        buf,
                        caption=text or None,
                        reply_to=topic_id,
                        force_document=not is_photo,
                        mime_type=mime_type,
                        attributes=None
                    )
                elif text:
                    await bot_client.send_message(
                        TARGET_CHAT_ID,
                        text,
                        reply_to=topic_id,
                        link_preview=False
                    )
                published += 1
                log(f"✅ Опубликовано исходное msg_id={m.id}")

        except errors.FloodWaitError as e:
            log(f"⏳ FloodWait {e.seconds}s – пауза…")
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            log(f"⚠️ {e}")

        log(f"Проверка завершена, новых сообщений: {published}")
        await asyncio.sleep(120)


async def main():
    await ensure_authorized()

    sources = [
        {
            "channel": "ВСТАВИТЬ НАЗВАНИЕ ГРУППЫ",
            "topic_id": #id,
            "formatter": format_koltrack
        },
        {
            "channel": "ВСТАВИТЬ НАЗВАНИЕ ГРУППЫ,
            "topic_id": #id,
            "formatter": format_rugpull
        }
    ]

    tasks = []
    for src in sources:
        entity = await user_client.get_entity(src["channel"])
        tasks.append(process_new_messages(entity, src["topic_id"], src["formatter"]))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    with user_client, bot_client:
        user_client.loop.run_until_complete(main())
