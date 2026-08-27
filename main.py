import os
import json
from threading import Thread
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = "8048885469:AAEc_iOxnCJI-6M7DIH5M1rK_KiznHddjoo"
ADMIN_ID = 6682139161

# --- Flask server ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running 24/7!"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    t = Thread(target=run_web)
    t.start()
# --------------------

def load_data(filename, default):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default
    return default

def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

users = load_data("users.json", {})
catalog = load_data("catalog.json", [])
channels = load_data("channels.json", []) 
admins = load_data("admins.json", [ADMIN_ID])

vip_settings = load_data("vip_settings.json", {"card": "8600 0000 0000 0000", "channel_id": ""})

bot_texts = load_data("bot_texts.json", {
    "start": "🎬 Xush kelibsiz! Kino yoki multfilm kodini yuboring.",
    "sub": "⚠️ Botimizdan to'liq foydalanish uchun quyidagi kanallarga obuna bo'ling:",
    "not_found": "Bunday kino topilmadi❌",
    "vip_tariffs": "💎 VIP obuna orqali barcha cheklovlarni olib tashlang!"
})

ADMIN_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("📊 Statistika"), KeyboardButton("🎬 Kino boshqaruvi")],
    [KeyboardButton("🎁 Referal"), KeyboardButton("📢 Majburiy obuna")],
    [KeyboardButton("👥 Foydalanuvchilar"), KeyboardButton("👮‍♂️ Adminlar")],
    [KeyboardButton("📢 Reklama"), KeyboardButton("💎 VIP boshqaruv")],
    [KeyboardButton("🔍 ID qidirish"), KeyboardButton("ℹ️ Sozlamalar")]
], resize_keyboard=True)

USER_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("🎬 Kino va multfilm kodlari"), KeyboardButton("💎 VIP status")],
    [KeyboardButton("🎁 Referal"), KeyboardButton("👤 Profil")],
    [KeyboardButton("📞 Aloqa")]
], resize_keyboard=True)

async def check_telegram_subscription(bot, user_id):
    if user_id == ADMIN_ID or user_id in admins:
        return True
    if str(user_id) in users and users.get(str(user_id), {}).get("vip", False):
        return True

    tg_channels = [ch for ch in channels if isinstance(ch, dict) and ch.get("type", "tg") == "tg"]
    if not tg_channels:
        return True

    for ch in tg_channels:
        url = ch.get("url", "")
        clean_ch = url.replace("https://t.me/", "").replace("@", "").strip()
        if not clean_ch:
            continue
        try:
            chat_target = int(clean_ch) if clean_ch.startswith("-100") or clean_ch.lstrip("-").isdigit() else f"@{clean_ch}"
            member = await bot.get_chat_member(chat_id=chat_target, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            print(f"Obunani tekshirishda xatolik: {e}")
            return False
    return True

async def send_subscription_required(update_or_query, pending_code=None):
    query = getattr(update_or_query, "callback_query", None)
    message = query.message if query else update_or_query.message
    
    keyboard_buttons = []
    for ch in channels:
        if not isinstance(ch, dict):
            continue
        if ch.get("type") == "social":
            keyboard_buttons.append([InlineKeyboardButton(f"🌐 {ch.get('name', 'Link')}", url=ch.get("url", "https://t.me"))])
        else:
            url = ch.get("url", "")
            clean_ch = url.replace("https://t.me/", "").replace("@", "").strip()
            if clean_ch:
                channel_link = f"https://t.me/{clean_ch}" if not clean_ch.startswith("-") else url
                keyboard_buttons.append([InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=channel_link)])
    
    cb_data = f"check_sub_{pending_code}" if pending_code else "check_sub"
    keyboard_buttons.append([InlineKeyboardButton("✅ Obunani tekshirish", callback_data=cb_data)])
    
    try:
        await message.reply_text(bot_texts["sub"], reply_markup=InlineKeyboardMarkup(keyboard_buttons))
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    context.user_data["state"] = None
    
    if user_id not in users:
        users[user_id] = {"name": user.full_name, "vip": False, "referrals": []}
        save_data("users.json", users)

    is_admin = (user.id in admins or user.id == ADMIN_ID)
    
    if is_admin:
        await update.message.reply_text("👋 Xush kelibsiz, Hurmatli Admin!", reply_markup=ADMIN_KEYBOARD)
        return

    await update.message.reply_text(bot_texts["start"], reply_markup=USER_KEYBOARD)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    is_admin = (user_id in admins or user_id == ADMIN_ID)
    text = update.message.text.strip() if update.message.text else ""
    
    state = context.user_data.get("state")

    if is_admin and state:
        if state == "waiting_for_channel":
            context.user_data["state"] = None
            channels.append({"url": text, "type": "tg"})
            save_data("channels.json", channels)
            await update.message.reply_text(f"✅ Kanal ulandi: {text}", reply_markup=ADMIN_KEYBOARD)
            return
        elif state == "waiting_for_movie_file":
            file_id = update.message.video.file_id if update.message.video else (update.message.document.file_id if update.message.document else update.message.photo[-1].file_id)
            context.user_data["temp_movie_file_id"] = file_id
            context.user_data["state"] = "waiting_for_movie_name"
            await update.message.reply_text("✍️ Kinoning nomini yozing:")
            return
        elif state == "waiting_for_movie_name":
            new_code = str(len(catalog) + 1)
            catalog.append({"code": new_code, "title": text, "file_id": context.user_data.get("temp_movie_file_id")})
            save_data("catalog.json", catalog)
            context.user_data["state"] = None
            await update.message.reply_text(f"✅ Kino qo'shildi!\n📌 Kod: {new_code}", reply_markup=ADMIN_KEYBOARD)
            return
        elif state == "waiting_for_ad":
            context.user_data["state"] = None
            count = sum(1 for uid in users if await try_send_ad(context.bot, uid, update.message))
            await update.message.reply_text(f"✅ Reklama {count} ta odamga yuborildi!", reply_markup=ADMIN_KEYBOARD)
            return
        elif state == "waiting_for_new_admin":
            context.user_data["state"] = None
            try:
                admins.append(int(text))
                save_data("admins.json", admins)
                await update.message.reply_text("✅ Admin qo'shildi!", reply_markup=ADMIN_KEYBOARD)
            except:
                await update.message.reply_text("❌ Faqat raqam kiriting!", reply_markup=ADMIN_KEYBOARD)
            return
        elif state == "waiting_for_vip_card":
            context.user_data["state"] = None
            vip_settings["card"] = text
            save_data("vip_settings.json", vip_settings)
            await update.message.reply_text("✅ Karta yangilandi!", reply_markup=ADMIN_KEYBOARD)
            return
        elif state == "waiting_for_search_id":
            context.user_data["state"] = None
            found = next((item for item in catalog if str(item.get("code")) == text), None)
            if found:
                await update.message.reply_video(video=found["file_id"], caption=f"🎬 {found['title']}\n📌 Kod: {found['code']}")
            else:
                await update.message.reply_text("❌ Topilmadi")
            return

    if is_admin:
        if text == "🎬 Kino boshqaruvi":
            await update.message.reply_text("🎬 Kino boshqaruvi:", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Kino qo'shish", callback_data="add_movie")],
                [InlineKeyboardButton("🗑 Kino o'chirish", callback_data="del_movie_menu")],
                [InlineKeyboardButton("🔙 Panel", callback_data="back_to_admin")]
            ]))
            return
        elif text == "📢 Majburiy obuna":
            await update.message.reply_text("📢 Majburiy obuna:", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📌 Kanal ulash", callback_data="add_channel")],
                [InlineKeyboardButton("📋 Ro'yxat", callback_data="list_channels")],
                [InlineKeyboardButton("🔙 Panel", callback_data="back_to_admin")]
            ]))
            return
        elif text == "ℹ️ Sozlamalar":
            await update.message.reply_text("ℹ️ Sozlamalar:", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Panel", callback_data="back_to_admin")]
            ]))
            return
        elif text == "👥 Foydalanuvchilar":
            await update.message.reply_text(f"👥 Foydalanuvchilar soni: {len(users)} ta", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]
            ]))
            return
        elif text == "👮‍♂️ Adminlar":
            await update.message.reply_text("👮‍♂️ Adminlar menyusi:", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Admin qo'shish", callback_data="add_admin")],
                [InlineKeyboardButton("📋 Ro'yxat", callback_data="list_admins")],
                [InlineKeyboardButton("🔙 Panel", callback_data="back_to_admin")]
            ]))
            return
        elif text == "💎 VIP boshqaruv":
            await update.message.reply_text(f"💳 Karta: {vip_settings['card']}", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Karta o'zgartirish", callback_data="change_vip_card")],
                [InlineKeyboardButton("🔙 Panel", callback_data="back_to_admin")]
            ]))
            return
        elif text == "📊 Statistika":
            await update.message.reply_text(f"📊 Statistika:\n👥 Foydalanuvchilar: {len(users)}\n🎬 Kinolar: {len(catalog)}")
            return
        elif text == "📢 Reklama":
            context.user_data["state"] = "waiting_for_ad"
            await update.message.reply_text("📢 Reklama postini yuboring:")
            return
        elif text == "🔍 ID qidirish":
            context.user_data["state"] = "waiting_for_search_id"
            await update.message.reply_text("🔍 Kino kodini kiriting:")
            return

    found_movie = next((item for item in catalog if str(item.get("code")).strip().lower() == text.lower()), None)
    if found_movie:
        await update.message.reply_video(video=found_movie["file_id"], caption=f"🎬 {found_movie.get('title')}\n📌 Kod: {found_movie.get('code')}")
    else:
        await update.message.reply_text(bot_texts["not_found"])

async def try_send_ad(bot, uid, message):
    try:
        await message.copy(chat_id=int(uid))
        return True
    except:
        return False

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_to_admin":
        await query.message.edit_text("👑 Admin paneli:", reply_markup=None)
        await context.bot.send_message(chat_id=query.from_user.id, text="👑 Asosiy admin menyusi:", reply_markup=ADMIN_KEYBOARD)
    elif data == "add_admin":
        context.user_data["state"] = "waiting_for_new_admin"
        await query.message.edit_text("👮‍♂️ Yangi admin ID raqamini yuboring:")
    elif data == "list_admins":
        await query.message.edit_text(f"📋 Adminlar:\n" + "\n".join([str(a) for a in admins]))
    elif data == "change_vip_card":
        context.user_data["state"] = "waiting_for_vip_card"
        await query.message.edit_text("💳 Yangi karta raqamini yuboring:")
    elif data == "add_channel":
        context.user_data["state"] = "waiting_for_channel"
        await query.message.edit_text("📌 Kanal username yuboring:")
    elif data == "list_channels":
        await query.message.edit_text("📋 Kanallar:\n" + "\n".join([str(c) for c in channels]))
    elif data == "add_movie":
        context.user_data["state"] = "waiting_for_movie_file"
        await query.message.edit_text("🎬 Kinoni yuboring:")

def main():
    keep_alive()
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    print("Bot ishga tushdi...")
    application.run_polling()

if __name__ == "__main__":
    main()
