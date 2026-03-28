from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler

from bot.ai_client import AIClient
from bot.config import load_settings
from bot.main import TelegramAPI, handle_command, process_text_message
from bot.storage import Storage


class handler(BaseHTTPRequestHandler):
    def _reply(self, status: int, payload: dict) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def do_POST(self) -> None:  # noqa: N802
        secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
        if secret:
            got = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if got != secret:
                self._reply(403, {"ok": False, "error": "forbidden"})
                return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length).decode("utf-8")
            update = json.loads(raw)

            settings = load_settings()
            tg = TelegramAPI(settings.telegram_token)
            storage = Storage(settings.db_path)
            ai = AIClient(settings.groq_api_key, settings.model_name)

            message = update.get("message") or update.get("edited_message")
            if not message:
                self._reply(200, {"ok": True, "skipped": True})
                return

            chat = message.get("chat", {})
            user = message.get("from", {})
            chat_id = int(chat.get("id"))
            user_id = int(user.get("id", 0))

            storage.upsert_chat(
                chat_id=chat_id,
                title=str(chat.get("title") or user.get("first_name") or "Unknown"),
                chat_type=str(chat.get("type", "private")),
            )

            text = message.get("text")
            if text:
                if text.startswith("/") and handle_command(
                    command_text=text,
                    chat_id=chat_id,
                    user_id=user_id,
                    tg=tg,
                    storage=storage,
                    settings=settings,
                ):
                    self._reply(200, {"ok": True, "command": True})
                    return

                process_text_message(
                    text=text,
                    chat_id=chat_id,
                    user=user,
                    tg=tg,
                    storage=storage,
                    ai=ai,
                    settings=settings,
                )

            self._reply(200, {"ok": True})
        except Exception as exc:  # pragma: no cover
            self._reply(500, {"ok": False, "error": str(exc)})

    def do_GET(self) -> None:  # noqa: N802
        self._reply(200, {"ok": True, "service": "fleet-bot-webhook"})
