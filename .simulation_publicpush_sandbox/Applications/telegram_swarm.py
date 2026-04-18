import os
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

CONFIG_PATH = "sifta_channels.json"

def _load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _resolve_credentials() -> tuple[str, str]:
    """Env-first credential resolution.
    TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from environment override file values.
    """
    cfg = _load_config()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or str(cfg.get("TELEGRAM_BOT_TOKEN", "")).strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or str(cfg.get("TELEGRAM_CHAT_ID", "")).strip()
    return token, chat_id

def _mask_token(token: str) -> str:
    if len(token) < 12:
        return "***"
    return f"{token[:7]}...{token[-5:]}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('SIFTA Telegram Bridge Active. The Swarm is listening.')

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("pong ✅ | AliceM5Bot operational")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg_chat = context.application.bot_data.get("target_chat_id", "")
    await update.message.reply_text(
        "SIFTA Telegram Bridge Status\n"
        f"- Target chat configured: {'yes' if cfg_chat else 'no'}\n"
        f"- Polling mode: active\n"
        "- Commands: /start /ping /status"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_msg = (update.message.text or "").strip()
    sender = update.effective_user.username or update.effective_user.first_name or "unknown"
    chat_id = str(update.effective_chat.id) if update.effective_chat else "?"
    # TODO: Route user_msg into the SIFTA Relay or Agent loop
    # For now, it echoes connectivity + metadata.
    reply = (
        "[SWARM RECEIPT]\n"
        f"- sender: {sender}\n"
        f"- chat_id: {chat_id}\n"
        f"- payload: {user_msg}"
    )
    await update.message.reply_text(reply)

async def on_startup(app: Application) -> None:
    chat_id = app.bot_data.get("target_chat_id", "")
    if chat_id:
        try:
            await app.bot.send_message(
                chat_id=chat_id,
                text="SIFTA Telegram Bridge booted ✅ (AliceM5Bot online).",
            )
        except Exception as e:
            print(f"[WARN] Startup ping failed: {e}")

def main():
    token, target_chat_id = _resolve_credentials()
    if not token:
        print("No Telegram token found! Set TELEGRAM_BOT_TOKEN or run Setup GUI.")
        return

    print("╔══════════════════════════════════════════════╗")
    print("║ SIFTA SWARM — Telegram Channel Active        ║")
    print("╚══════════════════════════════════════════════╝")
    print(f"[TELEGRAM] token={_mask_token(token)} target_chat={'set' if target_chat_id else 'unset'}")

    app = Application.builder().token(token).post_init(on_startup).build()
    app.bot_data["target_chat_id"] = target_chat_id

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == '__main__':
    main()
