import os
import io
import random
import string
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, InputSticker
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, PreCheckoutQueryHandler, CallbackQueryHandler
from adsun import AsyncAdsunBot
from adsun.integrations.ptb import send_ad

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADSUN_TOKEN = os.environ.get("ADSUN_TOKEN")   # Account Token из Adsun
ADSUN_BLOCK_ID = os.environ.get("ADSUN_BLOCK_ID")  # числовой Block ID
PRICE_STARS = 100
BOT_USERNAME = "my_sticker_maker_bot"  # замените на username вашего бота (без @)

ads = AsyncAdsunBot(token=ADSUN_TOKEN, block_id=ADSUN_BLOCK_ID)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Отправь мне картинку, и я создам стикерпак.\n\n"
        f"Бесплатно: 3 пака в день\n"
        f"Безлимит: {PRICE_STARS} Stars (разово)"
    )

async def show_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ рекламы (вызывается после создания стикера или по команде)"""
    u = update.effective_user
    try:
        await send_ad(context.bot, update.effective_chat.id, ads, u.id, u.language_code or "en")
    except Exception:
        pass  # если рекламы нет или ошибка — молча пропускаем

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    count = context.user_data.get("count", 0)
    unlimited = context.user_data.get("unlimited", False)

    if not unlimited and count >= 3:
        keyboard = [[InlineKeyboardButton(f"Купить безлимит за {PRICE_STARS} Stars", callback_data="buy")]]
        await update.message.reply_text(
            "Бесплатный лимит исчерпан. Купи безлимит:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    photo = update.message.photo[-1]
    file = await photo.get_file()
    img_bytes = await file.download_as_bytearray()
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

    # Обрезаем до квадрата, изменяем размер до 512x512 (требование стикерпака)
    w, h = img.size
    size = min(w, h)
    img = img.crop(((w - size) // 2, (h - size) // 2, (w + size) // 2, (h + size) // 2))
    img = img.resize((512, 512), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    # Генерируем уникальное имя пака: должно заканчиваться на _by_<bot_username>
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    pack_name = f"pack_{user_id}_{suffix}_by_{BOT_USERNAME}"
    # Ссылка на бота встраивается в НАЗВАНИЕ пака — это и есть бесплатное распространение
    pack_title = f"Создай свой: t.me/{BOT_USERNAME}"

    try:
        await context.bot.create_new_sticker_set(
            user_id=user_id,
            name=pack_name,
            title=pack_title,
            stickers=[InputSticker(sticker=buf, emoji="✨", format="static")],
        )
        link = f"https://t.me/addstickers/{pack_name}"
        await update.message.reply_text(
            f"Стикерпак создан!\nДобавь его: {link}\n\n"
            f"В названии пака уже есть ссылка на бота — когда кто-то добавит пак, он увидит её."
        )
    except Exception as e:
        await update.message.reply_text(f"Не удалось создать пак: {e}")
        return

    context.user_data["count"] = count + 1
    await update.message.reply_text(f"Осталось бесплатных: {3 - count - 1}" if not unlimited else "Безлимит активен")

    # После создания пака показываем рекламу (доход без дополнительных действий)
    await show_ad(update, context)

async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title="Безлимит",
        description="Неограниченное создание стикерпаков",
        payload="unlimited",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice("Безлимит", PRICE_STARS)],
    )

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["unlimited"] = True
    await update.message.reply_text("Оплата получена! Теперь создавай паки без ограничений.")

async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await context.bot.get_my_star_balance()
    await update.message.reply_text(f"Баланс Stars: {result.amount}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", check_balance))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern="buy"))
    app.run_polling()

if __name__ == "__main__":
    main()