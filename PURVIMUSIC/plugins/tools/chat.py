import re
import requests
import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatAction
from PURVIMUSIC import app

# system prompt.
SYS_PROMPT = "You are a sweet, friendly, and positive chatbot who chats in Hinglish. Keep your replies short, natural, and casual like a best friend talking on Telegram. Use emojis like 😊🙌✨❤️😘 and Hinglish phrases like 'Kya haal hai yaar?', 'Maza aa gaya!', or 'Aap toh kamaal hai yrr!'. Sound warm, cheerful, and helpful."

enabled_chats = {}

async def get_reply(msg):
    try:
        res = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            headers={"Content-Type": "application/json", "X-goog-api-key": "AIzaSyCMuV6nHtPQB-NExrfShffl38wiSZ2G-Tw"},
            json={"contents": [{"parts": [{"text": f"{SYS_PROMPT}\nUser: {msg}\nAssistant:"}]}]}
        )
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return "Arre yaar, kuch error aaya 😅 Thoda der baad try kar!"

@app.on_message(filters.command("start") & (filters.private | filters.group))
async def start(_, m):
    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Enable Bot", callback_data="enable")],
        [InlineKeyboardButton("❌ Disable Bot", callback_data="disable")]
    ])
    await m.reply_text("Hello doston! 😄 Main hoon aapka Hinglish dost! Start karein masti bhari baatein? ✨", reply_markup=btns)

@app.on_callback_query()
async def button_handler(client, callback_query):
    chat_id = callback_query.message.chat.id
    data = callback_query.data

    if data == "enable":
        enabled_chats[chat_id] = True
        await callback_query.answer("Bot enabled in this chat ✅", show_alert=True)
        await callback_query.edit_message_text("Yay! Bot is now ACTIVE 😊")
    elif data == "disable":
        enabled_chats[chat_id] = False
        await callback_query.answer("Bot disabled in this chat ❌", show_alert=True)
        await callback_query.edit_message_text("Okay! Bot is now OFF 💤")

@app.on_message((filters.text & ~filters.command("start")) & (filters.private | filters.group))
async def talk(client, m: Message):
    chat_id = m.chat.id
    text = m.text.lower()

    if not enabled_chats.get(chat_id, True):
        return

    # Check if the bot is mentioned in the message
    bot_username = (await client.get_me()).username.lower()
    is_mentioned = False

    if m.entities:
        for entity in m.entities:
            if entity.type == "mention" and m.text[entity.offset:entity.offset + entity.length].lower() == bot_username:
                is_mentioned = True
                break

    # Only respond if the bot is mentioned or in a private chat
    if not is_mentioned and not m.chat.type == "private":
        return

    await client.send_chat_action(chat_id, ChatAction.TYPING)
    await asyncio.sleep(0.5)

    if any(re.search(p, text) for p in [
        r"owner kaun hai", r"kon hai owner", r"who is your owner",
        r"owner kiska hai", r"tera owner", r"who made you",
        r"kisne banaya", r"creator kaun hai"
    ]):
        await m.reply_text("Mera Owner Deep hai! 😎 Bahut hi awesome banda h milna h to @its_deep_ydv msg kr lo!")
    else:
        reply = await get_reply(text)
        await m.reply_text(reply)
