import os


class Config:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "dolphin-mixtral")
    MEMORY_FILE = os.getenv("MEMORY_FILE", "memory_store.json")
    MAX_HISTORY_MESSAGES = 5
    MAX_RESPONSE_TOKENS = 100
    OPENROUTER_TEMPERATURE = 0.7
    OPENROUTER_TOP_P = 0.9
    FALLBACK_MESSAGE = "hmm... something broke, try again :/"
    OPENROUTER_ERROR_MESSAGE = "hmm… something broke, try again 😒"
    APP_NAME = os.getenv("APP_NAME", "Bunny Baby V2 Telegram Bot")
    APP_URL = os.getenv("APP_URL", "").strip()


def validate_telegram_token() -> None:
    if not Config.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable.")
