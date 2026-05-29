import asyncio
import logging
import json
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command

# --- SOZLAMALAR ---
BOT_TOKEN = "8664115718:AAHzRLf-nZnuPpCHACmWHFnGcLLBiYS6VXo"
ADMIN_ID = 6325088705

CHANNELS = [
    -1003731603684
    -1003999577501
    -1003912142197
    -5231904529
    -1003981536236
    # Qolgan kanallarni ham shu tartibda qo'shing (jami 5 ta)
]

DB_FILE = "sent_messages.json"


def load_db() -> dict:
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                raw = json.load(f)
            return {int(k): {int(ck): cv for ck, cv in v.items()} for k, v in raw.items()}
        except Exception:
            return {}
    return {}


def save_db(db: dict):
    with open(DB_FILE, "w") as f:
        json.dump({str(k): {str(ck): cv for ck, cv in v.items()} for k, v in db.items()}, f)


sent_messages_db: dict = load_db()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# --- RENDER.COM uchun Health Check ---
async def health_check(request):
    return web.Response(text="Bot ishlayapti!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Web server {PORT} portda ishga tushdi")


# --- BOT HANDLERLAR ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "👋 Assalomu alaykum Admin!\n\n"
            "📌 *Buyruqlar:*\n"
            "• Istalgan postni yuboring — kanallarga nusxalayman\n"
            "• Postni tahrirlasangiz — kanalda ham o'zgaradi\n"
            "• /delete — oxirgi postni o'chirish\n"
            "• /delete [raqam] — muayyan postni o'chirish\n"
            "• /list — yuborilgan postlar ro'yxati\n"
            "• /help — yordam",
            parse_mode="Markdown"
        )
    else:
        await message.answer("⛔ Siz bot admini emassiz!")


@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "📖 *Yordam:*\n\n"
        "Bot xabarlarni quyidagi kanallarga yuboradi:\n"
        + "\n".join(f"• `{ch}`" for ch in CHANNELS)
        + "\n\n"
        "Barcha media (rasm, video, fayl) ham qo'llab-quvvatlanadi.",
        parse_mode="Markdown"
    )


@dp.message(Command("list"))
async def list_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not sent_messages_db:
        await message.answer("📭 Hozircha yuborilgan post yo'q.")
        return
    lines = []
    for msg_id in list(sent_messages_db.keys())[-10:]:
        count = len(sent_messages_db[msg_id])
        lines.append(f"• Post ID: `{msg_id}` — {count} ta kanalda")
    await message.answer(
        "📋 *So'nggi 10 ta post:*\n" + "\n".join(lines),
        parse_mode="Markdown"
    )


@dp.message(Command("delete"))
async def delete_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) > 1:
        try:
            target_id = int(args[1])
        except ValueError:
            await message.answer("❌ Noto'g'ri format. Masalan: /delete 123")
            return
    else:
        if not sent_messages_db:
            await message.answer("📭 O'chirish uchun post topilmadi.")
            return
        target_id = list(sent_messages_db.keys())[-1]

    if target_id not in sent_messages_db:
        await message.answer(f"❌ ID {target_id} topilmadi.")
        return

    channels_data = sent_messages_db[target_id]
    deleted_count = 0
    for chat_id, msg_id in channels_data.items():
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            deleted_count += 1
        except Exception as e:
            logging.error(f"O'chirishda xatolik ({chat_id}): {e}")

    del sent_messages_db[target_id]
    save_db(sent_messages_db)
    await message.answer(f"🗑 Post {deleted_count} ta kanaldan o'chirildi!")


@dp.message()
async def broadcast_message(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    status_msg = await message.answer("🔄 Xabar kanallarga yuborilmoqda...")
    sent_messages_db[message.message_id] = {}
    success_count = 0
    failed_channels = []

    for chat_id in CHANNELS:
        try:
            copied_msg = await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            sent_messages_db[message.message_id][chat_id] = copied_msg.message_id
            success_count += 1
            await asyncio.sleep(0.3)
        except Exception as e:
            logging.error(f"Xatolik {chat_id} kanalida: {e}")
            failed_channels.append(chat_id)

    save_db(sent_messages_db)

    result_text = f"✅ Xabar {success_count}/{len(CHANNELS)} ta kanalga yuborildi!\n📌 Post ID: `{message.message_id}`"
    if failed_channels:
        result_text += f"\n⚠️ Muvaffaqiyatsiz: {len(failed_channels)} ta kanal"
    await status_msg.edit_text(result_text, parse_mode="Markdown")


@dp.edited_message()
async def edit_broadcast_message(edited_message: types.Message):
    if edited_message.from_user.id != ADMIN_ID:
        return
    if edited_message.message_id not in sent_messages_db:
        return

    channels_data = sent_messages_db[edited_message.message_id]
    edited_count = 0

    for chat_id, msg_id in channels_data.items():
        try:
            if edited_message.text:
                await bot.edit_message_text(
                    text=edited_message.text,
                    chat_id=chat_id,
                    message_id=msg_id,
                    entities=edited_message.entities
                )
            elif edited_message.caption:
                await bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=msg_id,
                    caption=edited_message.caption,
                    caption_entities=edited_message.caption_entities
                )
            edited_count += 1
            await asyncio.sleep(0.2)
        except Exception as e:
            logging.error(f"Tahrirlashda xatolik ({chat_id}): {e}")

    logging.info(f"Post {edited_message.message_id} {edited_count} ta kanalda yangilandi")


async def main():
    logging.info("Bot ishga tushmoqda...")
    logging.info(f"Admin ID: {ADMIN_ID}")
    logging.info(f"Kanallar soni: {len(CHANNELS)}")
    await start_web_server()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
