import os
import json
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

CONFIG_PATH = "sifta_channels.json"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('SIFTA Telegram Bridge Active. The Swarm is listening.')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_msg = update.message.text
    # TODO: Route user_msg into the SIFTA Relay or Agent loop
    # For now, it echoes that it's connected.
    reply = f"[SWARM RECEIPT]: Acknowledged your message: {user_msg}"
    await update.message.reply_text(reply)

def main():
    if not os.path.exists(CONFIG_PATH):
        print("sifta_channels.json not found. Please run the setup GUI.")
        return
        
    try:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
    except:
        config = {}
        
    token = config.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("No Telegram token found! Setup Telegram via the Setup GUI.")
        return

    print("╔══════════════════════════════════════════════╗")
    print("║ SIFTA SWARM — Telegram Channel Active        ║")
    print("╚══════════════════════════════════════════════╝")
    
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == '__main__':
    main()
