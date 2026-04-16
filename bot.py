import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import Config, validate_telegram_token
from llm import LLMClient
from memory import DEFAULT_USER_MODEL, MemoryStore
from prompt import build_messages


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

memory_store = MemoryStore()
llm_client = LLMClient()

MODEL_OPTIONS = {
    "model_r1": {
        "model": "deepseek/deepseek-r1",
        "label": "Sara (DeepSeek R1)",
        "mode_reply": "Sara mode selected 😏",
        "mode_name": "Sara (DeepSeek R1)",
    },
    "model_mistral": {
        "model": "mistralai/mixtral-8x7b-instruct",
        "label": "Madelyn Mommy (Mistral)",
        "mode_reply": "Madelyn Mommy mode selected 💀",
        "mode_name": "Madelyn Mommy (Mistral)",
    },
}


def build_model_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    MODEL_OPTIONS["model_r1"]["label"],
                    callback_data="model_r1",
                )
            ],
            [
                InlineKeyboardButton(
                    MODEL_OPTIONS["model_mistral"]["label"],
                    callback_data="model_mistral",
                )
            ],
        ]
    )


def describe_model(model: str) -> str:
    for option in MODEL_OPTIONS.values():
        if option["model"] == model:
            return option["mode_name"]
    return "Sara (DeepSeek R1)"


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
        "Select Bunny mode:",
        reply_markup=build_model_keyboard(),
    )


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if not update.effective_user or not update.message:
        return

    user_memory = memory_store.get_user_memory(update.effective_user.id)
    current_model = user_memory.get("model", DEFAULT_USER_MODEL)
    await update.message.reply_text(f"Current mode: {describe_model(current_model)}")


async def handle_model_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    del context
    if not update.callback_query or not update.effective_user:
        return

    query = update.callback_query
    option = MODEL_OPTIONS.get(query.data or "")
    if not option:
        await query.answer()
        return

    memory_store.set_user_model(update.effective_user.id, option["model"])
    await query.answer()
    await query.edit_message_text(option["mode_reply"])


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
    selected_model = user_memory.get("model", DEFAULT_USER_MODEL)

    # Step 5: construct prompt.
    messages = build_messages(
        user_message=user_message,
        mode=mode,
        history=user_memory.get("messages", []),
    )

    # Step 6: call OpenRouter API.
    try:
        reply_text = await asyncio.to_thread(
            llm_client.generate_reply,
            messages,
            selected_model,
        )
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
    application.add_handler(CommandHandler("mode", mode_command))
    application.add_handler(CallbackQueryHandler(handle_model_selection))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    print("Bunny Baby V2 bot is running...")
    application.run_polling()


if __name__ == "__main__":
    main()
