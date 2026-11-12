import os
import io
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, PreCheckoutQueryHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN")
PRICE_STARS = 100  # 100 Stars за безлимит

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Отправь мне картинку, и я нарежу её на эмодзи-паки.\n\n"
        f"Бесплатно: 3 пака в день\n"
        f"Безлимит: {PRICE_STARS} Stars (разово)"
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверка лимита (упрощённо: бесплатно 3 раза, потом просим оплату)
    user_id = update.effective_user.id
    count = context.user_data.get("count", 0)
    
    if count >= 3:
        keyboard = [[InlineKeyboardButton(f"Купить безлимит за {PRICE_STARS} Stars", callback_data="buy")]]
        await update.message.reply_text(
            "Бесплатный лимит исчерпан. Купи безлимит, чтобы продолжить:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    photo = update.message.photo[-1]
    file = await photo.get_file()
    img_bytes = await file.download_as_bytearray()
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    
    # Нарезаем на квадраты 100x100
    w, h = img.size
    size = min(w, h)
    img = img.crop(((w-size)//2, (h-size)//2, (w+size)//2, (h+size)//2))
    img = img.resize((100, 100), Image.LANCZOS)
    
    # Отправляем обратно как документ (пользователь может добавить в стикеры)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    await update.message.reply_document(document=buf, filename="emoji.png")
    
    context.user_data["count"] = count + 1
    await update.message.reply_text(f"Готово! Осталось бесплатных: {3 - count - 1}")

async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title="Безлимит",
        description="Неограниченное создание эмодзи-паков",
        payload="unlimited",
        provider_token="",  # для Stars пустая строка
        currency="XTR",
        prices=[LabeledPrice("Безлимит", PRICE_STARS)],
    )

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["unlimited"] = True
    context.user_data["count"] = 0
    await update.message.reply_text("Оплата получена! Теперь можешь создавать паки без ограничений.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(buy_callback, pattern="buy"))
    app.run_polling()

if __name__ == "__main__":
    main()