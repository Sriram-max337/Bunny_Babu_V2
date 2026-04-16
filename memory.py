import json
from pathlib import Path
from threading import Lock
from typing import Dict, List

from config import Config


class MemoryStore:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or Config.MEMORY_FILE)
        self._lock = Lock()

    def _read_all(self) -> Dict[str, Dict]:
        if not self.path.exists():
            return {}

        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_all(self, data: Dict[str, Dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def get_user_memory(self, user_id: int) -> Dict:
        with self._lock:
            data = self._read_all()
            user_key = str(user_id)
            return data.get(
                user_key,
                {
                    "messages": [],
                    "mood": "",
                    "last_mode": "",
                },
            )

    def save_interaction(
        self,
        user_id: int,
        user_message: str,
        assistant_message: str,
        mood: str,
        mode: str,
    ) -> None:
        with self._lock:
            data = self._read_all()
            user_key = str(user_id)
            entry = data.get(
                user_key,
                {
                    "messages": [],
                    "mood": "",
                    "last_mode": "",
                },
            )

            history: List[Dict[str, str]] = entry.get("messages", [])
            history.extend(
                [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_message},
                ]
            )

            entry["messages"] = history[-Config.MAX_HISTORY_MESSAGES :]
            entry["mood"] = mood
            entry["last_mode"] = mode
            data[user_key] = entry
            self._write_all(data)
