import json
import logging
import re
from typing import Dict, List
from urllib import error, request

from config import Config


logger = logging.getLogger(__name__)

MODEL_ALIASES = {
    "dolphin-mixtral": "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
    "mixtral": "mistralai/mixtral-8x7b-instruct",
}

MODEL_FALLBACKS = [
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
    "mistralai/mixtral-8x7b-instruct",
]
MAX_EMPTY_RESPONSE_RETRIES = 1


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

        for candidate_model in self._candidate_models(model or Config.OPENROUTER_MODEL):
            for attempt in range(MAX_EMPTY_RESPONSE_RETRIES + 1):
                max_tokens = Config.MAX_RESPONSE_TOKENS

                while True:
                    payload = {
                        "model": candidate_model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": Config.OPENROUTER_TEMPERATURE,
                        "top_p": Config.OPENROUTER_TOP_P,
                    }

                    try:
                        raw_body = self._post_chat_completion(payload)
                        data = json.loads(raw_body)
                        content = self._extract_content(data)
                        if content.strip():
                            return self.clean_response(content)

                        logger.warning(
                            "OpenRouter model '%s' returned empty content on attempt %s.",
                            candidate_model,
                            attempt + 1,
                        )
                        if attempt < MAX_EMPTY_RESPONSE_RETRIES:
                            continue
                        break
                    except error.HTTPError as exc:
                        details = exc.read().decode("utf-8", errors="ignore")
                        if exc.code == 400 and "not a valid model ID" in details:
                            logger.warning(
                                "OpenRouter model '%s' was rejected, trying fallback.",
                                candidate_model,
                            )
                            break
                        if exc.code == 402:
                            affordable_tokens = self._extract_affordable_tokens(details)
                            if affordable_tokens and affordable_tokens < max_tokens:
                                logger.warning(
                                    "OpenRouter credits are low; retrying model '%s' with max_tokens=%s.",
                                    candidate_model,
                                    affordable_tokens,
                                )
                                max_tokens = affordable_tokens
                                continue
                        if exc.code == 429:
                            logger.warning(
                                "OpenRouter model '%s' is rate-limited, trying fallback.",
                                candidate_model,
                            )
                            break
                        logger.exception("OpenRouter HTTP error: %s", details)
                        raise RuntimeError("OpenRouter request failed.") from exc
                    except error.URLError as exc:
                        logger.exception("OpenRouter connection error: %s", exc)
                        raise RuntimeError("OpenRouter request failed.") from exc
                    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
                        logger.exception("Invalid OpenRouter response")
                        raise RuntimeError("Invalid OpenRouter response.") from exc
                    except Exception as exc:
                        logger.exception("Unexpected OpenRouter error")
                        raise RuntimeError("OpenRouter request failed.") from exc

        raise RuntimeError("OpenRouter request failed.")

    @staticmethod
    def _extract_affordable_tokens(details: str) -> int | None:
        match = re.search(r"can only afford (\d+)", details)
        if not match:
            return None
        affordable_tokens = int(match.group(1))
        return affordable_tokens if affordable_tokens > 0 else None

    def _post_chat_completion(self, payload: Dict[str, object]) -> str:
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

        with request.urlopen(req, timeout=60) as response:
            return response.read().decode("utf-8")

    @staticmethod
    def _candidate_models(requested_model: str) -> List[str]:
        candidates: List[str] = []
        for item in (
            requested_model,
            MODEL_ALIASES.get(requested_model, ""),
            *MODEL_FALLBACKS,
        ):
            if item and item not in candidates:
                candidates.append(item)
        return candidates

    @staticmethod
    def _extract_content(data: Dict[str, object]) -> str:
        message = data["choices"][0]["message"]
        content = message.get("content")

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
            return "\n".join(parts)

        return ""

    @staticmethod
    def clean_response(content: str | None) -> str:
        if not content:
            return Config.FALLBACK_MESSAGE

        cleaned = "\n".join(
            line.strip() for line in content.strip().splitlines() if line.strip()
        )
        if not cleaned:
            return Config.FALLBACK_MESSAGE

        lines = cleaned.splitlines()[:3]
        return "\n".join(lines).strip() or Config.FALLBACK_MESSAGE
