"""
🤖 بوت توصيات فوركس
"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 إشارات", callback_data="signals"),
         InlineKeyboardButton("ℹ️ معلومات", callback_data="info")],
    ]
    await update.message.reply_text(
        "🤖 *بوت توصيات فوركس*\n\n"
        "✅ البوت يعمل الآن!\n"
        "💱 فوركس\n"
        "🪙 عملات رقمية\n"
        "🛢️ سلع (الذهب)\n\n"
        "⚠️ للأغراض التعليمية فقط",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "signals":
        await query.edit_message_text(
            "📊 *الإشارات الحالية*\n\n"
            "🟢 شراء قوي - EUR/USD @ 1.0950\n"
            "🎯 الهدف: 1.1050\n"
            "🛑 وقف الخسارة: 1.0900\n\n"
            "🔴 بيع - Bitcoin @ 45,000\n"
            "🎯 الهدف: 44,000\n"
            "🛑 وقف الخسارة: 46,000",
            parse_mode="Markdown"
        )
    elif query.data == "info":
        await query.edit_message_text(
            "ℹ️ *معلومات البوت*\n\n"
            "✅ إشارات شراء/بيع\n"
            "✅ تارقت ووقف خسارة\n"
            "✅ تحليل تقني\n\n"
            "⚠️ للأغراض التعليمية فقط",
            parse_mode="Markdown"
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/start للبدء")

def main():
    print("🚀 جاري تشغيل البوت...")
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ البوت يعمل!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
