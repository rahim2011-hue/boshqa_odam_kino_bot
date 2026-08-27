import os
import json
from threading import Thread
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = "8048885469:AAEnaKkGkGk7ssR28fy6MjPW201YP1eSig8"
ADMIN_ID = 6682139161

# --- Flask server (Render 24/7 ishlashi uchun) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running 24/7!"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    t = Thread(target=run_web)
    t.start()
# ----------------------------------------------------

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
            print(f"Obunani tekshirishda xatolik ({clean_ch}): {e}")
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
    pending_code = None

    if context.args:
        arg = context.args[0].strip()
        if arg.startswith("ref_"):
            ref_id = arg.replace("ref_", "")
            if ref_id in users and ref_id != user_id:
                if user_id not in users[ref_id]["referrals"]:
                    users[ref_id]["referrals"].append(user_id)
                    save_data("users.json", users)
        else:
            pending_code = arg

    if not is_admin:
        is_subbed = await check_telegram_subscription(context.bot, user.id)
        if not is_subbed:
            await send_subscription_required(update, pending_code=pending_code)
            return

    if is_admin:
        await update.message.reply_text("👋 Xush kelibsiz, Hurmatli Admin!", reply_markup=ADMIN_KEYBOARD)
        return

    if pending_code:
        found_movie = next((item for item in catalog if str(item.get("code")).strip() == pending_code), None)
        if found_movie:
            await update.message.reply_video(
                video=found_movie["file_id"], 
                caption=f"🎬 {found_movie.get('title')}\n📌 Kod: {found_movie.get('code')}",
                reply_markup=USER_KEYBOARD
            )
            return
        else:
            await update.message.reply_text(bot_texts["not_found"], reply_markup=USER_KEYBOARD)
            return

    await update.message.reply_text(bot_texts["start"], reply_markup=USER_KEYBOARD)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    is_admin = (user_id in admins or user_id == ADMIN_ID)
    text = update.message.text.strip() if update.message.text else ""
    
    admin_menu_buttons = [
        "📊 Statistika", "🎬 Kino boshqaruvi", "🎁 Referal", 
        "📢 Majburiy obuna", "👥 Foydalanuvchilar", "👮‍♂️ Adminlar", 
        "📢 Reklama", "💎 VIP boshqaruv", "🔍 ID qidirish", "ℹ️ Sozlamalar"
    ]
    
    if is_admin and text in admin_menu_buttons:
        context.user_data["state"] = None

    state = context.user_data.get("state")

    if is_admin and state:
        if state == "waiting_for_channel":
            context.user_data["state"] = None
            clean_new_ch = text.strip()
            exists = any(c.get("url") == clean_new_ch for c in channels if isinstance(c, dict))
            if not exists:
                channels.append({"url": clean_new_ch, "type": "tg"})
                save_data("channels.json", channels)
                await update.message.reply_text(f"✅ Kanal muvaffaqiyatli ulandi: {clean_new_ch}", reply_markup=ADMIN_KEYBOARD)
            else:
                await update.message.reply_text("⚠️ Bu kanal allaqachon qo'shilgan!", reply_markup=ADMIN_KEYBOARD)
            return

        elif state == "waiting_for_movie_file":
            if not update.message.video and not update.message.document and not update.message.photo:
                await update.message.reply_text("❌ Kinoni video yoki fayl ko'rinishida yuboring!")
                return
            
            if update.message.video:
                file_id = update.message.video.file_id
            elif update.message.document:
                file_id = update.message.document.file_id
            else:
                file_id = update.message.photo[-1].file_id

            context.user_data["temp_movie_file_id"] = file_id
            context.user_data["state"] = "waiting_for_preview"
            await update.message.reply_text("📹 Kanalga tashlash uchun qisqa video yoki rasm yuboring:")
            return

        elif state == "waiting_for_preview":
            if not update.message.video and not update.message.photo and not update.message.document:
                await update.message.reply_text("❌ Iltimos, qisqa video yoki rasm yuboring!")
                return
            
            if update.message.video:
                prev_id = update.message.video.file_id
                prev_type = "video"
            elif update.message.photo:
                prev_id = update.message.photo[-1].file_id
                prev_type = "photo"
            else:
                prev_id = update.message.document.file_id
                prev_type = "document"

            context.user_data["temp_preview_id"] = prev_id
            context.user_data["temp_preview_type"] = prev_type
            context.user_data["state"] = "waiting_for_movie_name"
            await update.message.reply_text("✍️ Kinoning nomini yozing:")
            return

        elif state == "waiting_for_movie_name":
            movie_title = text
            new_code = str(len(catalog) + 1)
            file_id = context.user_data.get("temp_movie_file_id")
            prev_id = context.user_data.get("temp_preview_id")
            prev_type = context.user_data.get("temp_preview_type")
            
            new_movie_item = {
                "code": new_code, 
                "title": movie_title, 
                "file_id": file_id,
                "preview_id": prev_id,
                "preview_type": prev_type
            }
            
            catalog.append(new_movie_item)
            save_data("catalog.json", catalog)
            
            channel_target_raw = str(vip_settings.get("channel_id", "")).strip()
            if channel_target_raw:
                try:
                    bot_info = await context.bot.get_me()
                    bot_username = bot_info.username
                    
                    caption = f"🎬 {movie_title}\n📌 Kod: {new_code}\n\n🤖 Bizning bot: @{bot_username}\n👇 Ko'rish uchun quyidagi tugmani bosing:"
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("▶️ Ko'rish uchun bosing", url=f"https://t.me/{bot_username}?start={new_code}")]
                    ])

                    if channel_target_raw.startswith("-100") or channel_target_raw.lstrip("-").isdigit():
                        channel_chat_id = int(channel_target_raw)
                    else:
                        channel_chat_id = channel_target_raw if channel_target_raw.startswith("@") else f"@{channel_target_raw}"

                    if prev_type == "video":
                        await context.bot.send_video(chat_id=channel_chat_id, video=prev_id, caption=caption, reply_markup=keyboard)
                    elif prev_type == "photo":
                        await context.bot.send_photo(chat_id=channel_chat_id, photo=prev_id, caption=caption, reply_markup=keyboard)
                    else:
                        await context.bot.send_document(chat_id=channel_chat_id, document=prev_id, caption=caption, reply_markup=keyboard)
                except Exception as e:
                    print(f"Kanalga tashlashda xatolik: {e}")

            context.user_data["state"] = None
            await update.message.reply_text(f"✅ Kino muvaffaqiyatli qo'shildi va kanalga yuborildi!\n📌 Kod: {new_code}", reply_markup=ADMIN_KEYBOARD)
            return

        elif state == "waiting_for_ad":
            context.user_data["state"] = None
            count = 0
            for uid in users:
                try:
                    await update.message.copy(chat_id=int(uid))
                    count += 1
                except:
                    pass
            await update.message.reply_text(f"✅ Reklama {count} ta odamga yuborildi!", reply_markup=ADMIN_KEYBOARD)
            return

        elif state == "waiting_for_social":
            context.user_data["state"] = None
            context.user_data["temp_social_url"] = text
            context.user_data["state"] = "waiting_for_social_name"
            await update.message.reply_text("🌐 Tarmoq nomini kiriting:")
            return

        elif state == "waiting_for_social_name":
            context.user_data["state"] = None
            url = context.user_data.get("temp_social_url", "")
            exists = any(c.get("url") == url for c in channels if isinstance(c, dict))
            if not exists:
                channels.append({"url": url, "type": "social", "name": text})
                save_data("channels.json", channels)
                await update.message.reply_text(f"✅ Ulandi: {text}", reply_markup=ADMIN_KEYBOARD)
            else:
                await update.message.reply_text("⚠️ Bu havola allaqachon mavjud!", reply_markup=ADMIN_KEYBOARD)
            return

        elif state == "set_start_text_input":
            context.user_data["state"] = None
            bot_texts["start"] = text
            save_data("bot_texts.json", bot_texts)
            await update.message.reply_text("✅ Start matni yangilandi!", reply_markup=ADMIN_KEYBOARD)
            return

        elif state == "set_sub_text_input":
            context.user_data["state"] = None
            bot_texts["sub"] = text
            save_data("bot_texts.json", bot_texts)
            await update.message.reply_text("✅ Obuna matni yangilandi!", reply_markup=ADMIN_KEYBOARD)
            return

        elif state == "set_not_found_text_input":
            context.user_data["state"] = None
            bot_texts["not_found"] = text
            save_data("bot_texts.json", bot_texts)
            await update.message.reply_text("✅ Topilmadi matni yangilandi!", reply_markup=ADMIN_KEYBOARD)
            return

        elif state == "set_vip_text_input":
            context.user_data["state"] = None
            bot_texts["vip_tariffs"] = text
            save_data("bot_texts.json", bot_texts)
            await update.message.reply_text("✅ VIP matni yangilandi!", reply_markup=ADMIN_KEYBOARD)
            return

        elif state == "waiting_for_search_id":
            context.user_data["state"] = None
            found = next((item for item in catalog if str(item.get("code")).strip() == text.strip()), None)
            if found:
                await update.message.reply_video(video=found["file_id"], caption=f"🎬 {found['title']}\n📌 Kod: {found['code']}")
            else:
                await update.message.reply_text(bot_texts["not_found"])
            return

        elif state == "waiting_for_new_admin":
            context.user_data["state"] = None
            try:
                new_id = int(text)
                if new_id not in admins:
                    admins.append(new_id)
                    save_data("admins.json", admins)
                    await update.message.reply_text("✅ Admin qo'shildi!", reply_markup=ADMIN_KEYBOARD)
                else:
                    await update.message.reply_text("⚠️ Bu foydalanuvchi allaqachon admin!", reply_markup=ADMIN_KEYBOARD)
            except:
                await update.message.reply_text("❌ Xato ID format! Faqat raqam kiriting.", reply_markup=ADMIN_KEYBOARD)
            return

        elif state == "waiting_for_vip_card":
            context.user_data["state"] = None
            vip_settings["card"] = text
            save_data("vip_settings.json", vip_settings)
            await update.message.reply_text("✅ Karta yangilandi!", reply_markup=ADMIN_KEYBOARD)
            return

        elif state == "waiting_for_post_channel":
            context.user_data["state"] = None
            vip_settings["channel_id"] = text.strip()
            save_data("vip_settings.json", vip_settings)
            await update.message.reply_text(f"✅ Kino kanali ulandi: {text}", reply_markup=ADMIN_KEYBOARD)
            return

    if is_admin:
        if text == "🎬 Kino boshqaruvi":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Kino qo'shish", callback_data="add_movie")],
                [InlineKeyboardButton("🗑 Kino o'chirish", callback_data="del_movie_menu")],
                [InlineKeyboardButton("🔙 Panel", callback_data="back_to_admin")]
            ])
            await update.message.reply_text("🎬 Kino boshqaruvi:", reply_markup=keyboard)
            return

        elif text == "📢 Majburiy obuna":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📌 Kanal ulash", callback_data="add_channel")],
                [InlineKeyboardButton("🌐 Ijtimoiy link ulash", callback_data="add_social")],
                [InlineKeyboardButton("🗑 Kanal o'chirish", callback_data="del_channel_menu")],
                [InlineKeyboardButton("📋 Ro'yxat", callback_data="list_channels")],
                [InlineKeyboardButton("🔙 Panel", callback_data="back_to_admin")]
            ])
            await update.message.reply_text("📢 Majburiy obuna boshqaruvi:", reply_markup=keyboard)
            return

        elif text == "ℹ️ Sozlamalar":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎬 Start matni", callback_data="set_start_text")],
                [InlineKeyboardButton("📢 Obuna matni", callback_data="set_sub_text")],
                [InlineKeyboardButton("❌ Topilmadi matni", callback_data="set_not_found_text")],
                [InlineKeyboardButton("💎 VIP tariflar", callback_data="set_vip_text")],
                [InlineKeyboardButton("📢 Kino kanali (ID kiritish)", callback_data="set_post_channel")],
                [InlineKeyboardButton("🔙 Panel", callback_data="back_to_admin")]
            ])
            await update.message.reply_text(f"ℹ️ Bot sozlamalari:\n\n📢 Hozirgi ulangan kino kanali: `{vip_settings.get('channel_id', 'Kiritilmagan ❌')}`", reply_markup=keyboard, parse_mode="Markdown")
            return

        elif text == "👥 Foydalanuvchilar":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 Bot foydalanuvchilari", callback_data="bot_users_list")],
                [InlineKeyboardButton("📢 Kanal foydalanuvchilari", callback_data="channel_users_list")],
                [InlineKeyboardButton("🔙 Panel", callback_data="back_to_admin")]
            ])
            await update.message.reply_text("👥 Foydalanuvchilar bo'limini tanlang:", reply_markup=keyboard)
            return

        elif text == "👮‍♂️ Adminlar":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Admin qo'shish", callback_data="add_admin")],
                [InlineKeyboardButton("📋 Ro'yxat", callback_data="list_admins")],
                [InlineKeyboardButton("🔙 Panel", callback_data="back_to_admin")]
            ])
            await update.message.reply_text("👮‍♂️ Adminlar menyusi:", reply_markup=keyboard)
            return

        elif text == "💎 VIP boshqaruv":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Karta o'zgartirish", callback_data="change_vip_card")],
                [InlineKeyboardButton("🔙 Panel", callback_data="back_to_admin")]
            ])
            await update.message.reply_text(f"💳 Hozirgi karta: {vip_settings['card']}", reply_markup=keyboard)
            return

        elif text == "📊 Statistika":
            await update.message.reply_text(f"📊 Statistika:\n👥 Foydalanuvchilar: {len(users)}\n🎬 Kinolar: {len(catalog)}\n📢 Kanallar/Linklar: {len(channels)}")
            return

        elif text == "📢 Reklama":
            context.user_data["state"] = "waiting_for_ad"
            await update.message.reply_text("📢 Reklama postini yuboring:")
            return

        elif text == "🔍 ID qidirish":
            context.user_data["state"] = "waiting_for_search_id"
            await update.message.reply_text("🔍 Kino kodini kiriting:")
            return

    if not is_admin:
        is_subbed = await check_telegram_subscription(context.bot, user_id)
        if not is_subbed:
            await send_subscription_required(update)
            return

    user_id_str = str(user_id)

    if text == "🎁 Referal":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
        refs = users.get(user_id_str, {}).get("referrals", [])
        await update.message.reply_text(f"🎁 Referal havolangiz:\n{ref_link}\n\n👥 Takliflar: {len(refs)} ta")
        return

    if text == "🎬 Kino va multfilm kodlari":
        await update.message.reply_text("🔍 Ko'rmoqchi bo'lgan kino yoki multfilmingiz kodini yuboring:")
        return
    elif text == "💎 VIP status":
        is_vip = users.get(user_id_str, {}).get("vip", False)
        status_text = "Sizda VIP status mavjud! ✅" if is_vip else "Sizda hozircha VIP status yo'q ❌"
        vip_text = f"{bot_texts['vip_tariffs']}\n\nHolatingiz: {status_text}\n\nQuyidagi tariflardan birini tanlang:"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("1 oylik - 10,000 so'm", callback_data="vip_1")],
            [InlineKeyboardButton("3 oylik - 25,000 so'm", callback_data="vip_3")],
            [InlineKeyboardButton("Doimiy - 50,000 so'm", callback_data="vip_life")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")]
        ])
        await update.message.reply_text(vip_text, reply_markup=keyboard)
        return
    elif text == "👤 Profil":
        is_vip = users.get(user_id_str, {}).get("vip", False)
        await update.message.reply_text(f"👤 Profil:\n🆔 ID: {user_id}\n👤 Ism: {user.full_name}\n💎 VIP: {'Ha ✅' if is_vip else 'Yo\'q ❌'}")
        return
    elif text == "📞 Aloqa":
        await update.message.reply_text("📞 Admin bilan bog'lanish uchun: @proactive_11")
        return

    found_movie = next((item for item in catalog if str(item.get("code")).strip().lower() == text.lower()), None)
    if found_movie:
        await update.message.reply_video(
            video=found_movie["file_id"], 
            caption=f"🎬 {found_movie.get('title')}\n📌 Kod: {found_movie.get('code')}",
            reply_markup=USER_KEYBOARD
        )
    else:
        await update.message.reply_text(bot_texts["not_found"], reply_markup=USER_KEYBOARD)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    is_admin = (user_id in admins or user_id == ADMIN_ID)

    if data.startswith("check_sub"):
        if await check_telegram_subscription(context.bot, user_id):
            try: await query.message.delete()
            except: pass
            
            parts = data.split("_")
            if len(parts) > 2:
                movie_code = parts[2]
                found_movie = next((item for item in catalog if str(item.get("code")).strip() == movie_code), None)
                if found_movie:
                    await context.bot.send_video(
                        chat_id=user_id,
                        video=found_movie["file_id"],
                        caption=f"🎬 {found_movie.get('title')}\n📌 Kod: {found_movie.get('code')}",
                        reply_markup=USER_KEYBOARD
                    )
                    return

            await context.bot.send_message(chat_id=user_id, text="✅ Rahmat! Obuna tasdiqlandi.", reply_markup=USER_KEYBOARD)
        else:
            await query.answer("❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
        return

    if data.startswith("vip_"):
        card_num = vip_settings["card"]
        msg = f"💳 To'lov qilish uchun karta raqam:\n`{card_num}`\n\n📌 Pulni o'tkazib, chek rasmini yuboring!"
        await query.message.edit_text(msg, parse_mode="Markdown")
        return

    if data == "back_to_menu":
        context.user_data["state"] = None
        try: await query.message.delete()
        except: pass
        await context.bot.send_message(chat_id=user_id, text="🏠 Asosiy menyu:", reply_markup=USER_KEYBOARD)
        return

    if not is_admin:
        return

    if data == "back_to_admin":
        context.user_data["state"] = None
        try:
            await query.message.edit_text("👑 Admin paneli:", reply_markup=ADMIN_KEYBOARD)
        except:
            await query.message.delete()
            await context.bot.send_message(chat_id=user_id, text="👑 Admin paneli:", reply_markup=ADMIN_KEYBOARD)

    elif data == "bot_users_list":
        await query.message.edit_text(f"👥 Bot foydalanuvchilari soni: {len(users)} ta", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]]))

    elif data == "channel_users_list":
        tg_channels_count = sum(1 for c in channels if isinstance(c, dict) and c.get("type", "tg") == "tg")
        await query.message.edit_text(f"📢 Majburiy obunadagi kanallar soni: {tg_channels_count} ta", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]]))

    elif data == "add_admin":
        context.user_data["state"] = "waiting_for_new_admin"
        await query.message.edit_text("👮‍♂️ Yangi adminning Telegram ID raqamini yuboring:")

    elif data == "list_admins":
        admin_list_str = "\n".join([f"🆔 `{a}`" for a in admins])
        await query.message.edit_text(f"📋 Hozirgi adminlar ro'yxati:\n\n{admin_list_str}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]]))

    elif data == "change_vip_card":
        context.user_data["state"] = "waiting_for_vip_card"
        await query.message.edit_text("💳 Yangi karta raqamini kiriting:")

    elif data == "add_channel":
        context.user_data["state"] = "waiting_for_channel"
        await query.message.edit_text("📌 Kanal username yoki havolasini kiriting:")

    elif data == "add_social":
        context.user_data["state"] = "waiting_for_social"
        await query.message.edit_text("🌐 Ijtimoiy tarmoq havolasini yuboring:")

    elif data == "del_channel_menu":
        if not channels:
            await query.message.edit_text("❌ Hozircha ulangan kanallar yo'q.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]]))
            return
        keyboard = []
        for index, ch in enumerate(channels):
            url = ch.get("url", str(ch)) if isinstance(ch, dict) else str(ch)
            keyboard.append([InlineKeyboardButton(f"❌ O'chirish: {url}", callback_data=f"del_ch_{index}")])
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")])
        await query.message.edit_text("🗑 O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("del_ch_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(channels):
            removed = channels.pop(idx)
            save_data("channels.json", channels)
            rem_url = removed.get("url", str(removed)) if isinstance(removed, dict) else str(removed)
            
            if not channels:
                await query.message.edit_text(f"✅ O'chirildi: {rem_url}\n\n❌ Hozircha ulangan kanallar yo'q.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]]))
            else:
                keyboard = []
                for index, ch in enumerate(channels):
                    url = ch.get("url", str(ch)) if isinstance(ch, dict) else str(ch)
                    keyboard.append([InlineKeyboardButton(f"❌ O'chirish: {url}", callback_data=f"del_ch_{index}")])
                keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")])
                await query.message.edit_text(f"✅ O'chirildi: {rem_url}\n\n🗑 Boshqa kanalni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "list_channels":
        ch_list = "\n".join([f"{i+1}. {c.get('url', str(c))} ({c.get('type', 'tg')})" for i, c in enumerate(channels)]) if channels else "Hozircha yo'q."
        await query.message.edit_text(f"📋 Ulangan kanallar:\n\n{ch_list}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]]))

    elif data == "set_start_text":
        context.user_data["state"] = "set_start_text_input"
        await query.message.edit_text("🎬 Yangi Start matnini yuboring:")

    elif data == "set_sub_text":
        context.user_data["state"] = "set_sub_text_input"
        await query.message.edit_text("📢 Yangi Obuna matnini yuboring:")

    elif data == "set_not_found_text":
        context.user_data["state"] = "set_not_found_text_input"
        await query.message.edit_text("❌ Yangi Topilmadi matnini yuboring:")

    elif data == "set_vip_text":
        context.user_data["state"] = "set_vip_text_input"
        await query.message.edit_text("💎 Yangi VIP tariflar matnini yuboring:")

    elif data == "set_post_channel":
        context.user_data["state"] = "waiting_for_post_channel"
        await query.message.edit_text("📢 Kino kanali username yoki ID sini kiriting (masalan: `@kanal` yoki `-100...`):")

    elif data == "add_movie":
        context.user_data["state"] = "waiting_for_movie_file"
        await query.message.edit_text("🎬 Kinoni video yoki fayl ko'rinishida yuboring:")

    elif data == "del_movie_menu":
        if not catalog:
            await query.message.edit_text("❌ Kinolar mavjud emas.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]]))
            return
        keyboard = []
        for item in catalog:
            c_code = item.get("code")
            c_title = item.get("title")
            keyboard.append([InlineKeyboardButton(f"🗑 {c_code} - {c_title}", callback_data=f"del_movie_{c_code}")])
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")])
        await query.message.edit_text("🗑 O'chirmoqchi bo'lgan kinoni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("del_movie_"):
        movie_code = data.replace("del_movie_", "")
        
        catalog[:] = [item for item in catalog if str(item.get("code")) != movie_code]
        save_data("catalog.json", catalog)
        
        if not catalog:
            await query.message.edit_text("✅ Kino o'chirildi.\n\n❌ Kinolar qolmadi.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]]))
        else:
            keyboard = []
            for item in catalog:
                c_code = item.get("code")
                c_title = item.get("title")
                keyboard.append([InlineKeyboardButton(f"🗑 {c_code} - {c_title}", callback_data=f"del_movie_{c_code}")])
            keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")])
            await query.message.edit_text(f"✅ Kino o'chirildi!\n\n🗑 Boshqasini tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

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
