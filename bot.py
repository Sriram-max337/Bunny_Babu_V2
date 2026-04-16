import asyncio
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import Config, validate_telegram_token
from llm import LLMClient
from memory import MemoryStore
from prompt import build_messages


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

memory_store = MemoryStore()
llm_client = LLMClient()


def analyze_tone(text: str) -> str:
    lowered = text.lower()

    soft_signals = [
        "please",
        "soft",
        "gentle",
        "baby",
        "love",
        "miss you",
        "hug",
        "sweet",
        "care",
        "cute",
        "darling",
    ]
    playful_signals = [
        "hehe",
        "haha",
        "lol",
        "lmao",
        "play",
        "tease",
        "naughty",
        "brat",
        "challenge",
        "dare",
        "wink",
    ]

    if any(token in lowered for token in soft_signals):
        return "soft"
    if any(token in lowered for token in playful_signals) or "?" in lowered and "!" in lowered:
        return "playful"
    return "neutral"


def choose_mode(tone: str) -> str:
    mapping = {
        "soft": "SIA",
        "playful": "SARA",
        "neutral": "MOMMY",
    }
    return mapping.get(tone, "MOMMY")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    await update.message.reply_text(
        "Bunny Baby V2 is online. Send a message and I'll reply in character."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context

    if not update.effective_user or not update.message or not update.message.text:
        return

    # Step 1: receive the incoming Telegram message.
    user_id = update.effective_user.id
    user_message = update.message.text.strip()

    # Step 2: analyze tone.
    tone = analyze_tone(user_message)

    # Step 3: decide behavior mode.
    mode = choose_mode(tone)

    # Step 4: load memory.
    user_memory = memory_store.get_user_memory(user_id)

    # Step 5: construct prompt.
    messages = build_messages(
        user_message=user_message,
        mode=mode,
        history=user_memory.get("messages", []),
    )

    # Step 6: call OpenRouter API.
    try:
        reply_text = await asyncio.to_thread(llm_client.generate_reply, messages)
    except Exception:
        logger.exception("Failed to generate reply for Telegram user %s", user_id)
        reply_text = Config.OPENROUTER_ERROR_MESSAGE

    # Step 4 memory update after the turn finishes.
    memory_store.save_interaction(
        user_id=user_id,
        user_message=user_message,
        assistant_message=reply_text,
        mood=tone,
        mode=mode,
    )

    # Step 7: return response to Telegram.
    await update.message.reply_text(reply_text)


def main() -> None:
    validate_telegram_token()

    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    print("Bunny Baby V2 bot is running...")
    application.run_polling()


if __name__ == "__main__":
    main()
