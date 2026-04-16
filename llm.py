import json
import logging
from typing import Dict, List
from urllib import error, request

from config import Config


logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self) -> None:
        self._endpoint = f"{Config.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"

    def generate_reply(
        self,
        messages: List[Dict[str, str]],
        model: str | None = None,
    ) -> str:
        if not Config.OPENROUTER_API_KEY:
            raise RuntimeError("Missing OPENROUTER_API_KEY environment variable.")

        payload = {
            "model": model or Config.OPENROUTER_MODEL,
            "messages": messages,
            "max_tokens": Config.MAX_RESPONSE_TOKENS,
            "temperature": Config.OPENROUTER_TEMPERATURE,
            "top_p": Config.OPENROUTER_TOP_P,
        }

        headers = {
            "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }
        if Config.APP_URL:
            headers["HTTP-Referer"] = Config.APP_URL
        if Config.APP_NAME:
            headers["X-Title"] = Config.APP_NAME

        req = request.Request(
            self._endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=60) as response:
                raw_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            logger.exception("OpenRouter HTTP error: %s", details)
            raise RuntimeError("OpenRouter request failed.") from exc
        except error.URLError as exc:
            logger.exception("OpenRouter connection error: %s", exc)
            raise RuntimeError("OpenRouter request failed.") from exc
        except Exception as exc:
            logger.exception("Unexpected OpenRouter error")
            raise RuntimeError("OpenRouter request failed.") from exc

        try:
            data = json.loads(raw_body)
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            logger.exception("Invalid OpenRouter response: %s", raw_body)
            raise RuntimeError("Invalid OpenRouter response.") from exc

        return self.clean_response(content)

    @staticmethod
    def clean_response(content: str) -> str:
        cleaned = "\n".join(
            line.strip() for line in str(content).strip().splitlines() if line.strip()
        )
        if not cleaned:
            return Config.FALLBACK_MESSAGE

        lines = cleaned.splitlines()[:3]
        return "\n".join(lines).strip() or Config.FALLBACK_MESSAGE
