from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from .ai_client import AIClient
from .config import ConfigError, Settings, load_settings
from .storage import Storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("fleet-bot")


class TelegramAPI:
    def __init__(self, token: str) -> None:
        self.base_url = f"https://api.telegram.org/bot{token}"

    def call(self, method: str, payload: dict) -> dict:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/{method}",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            parsed = json.loads(response.read().decode("utf-8"))
        if not parsed.get("ok"):
            raise RuntimeError(f"Telegram API error on {method}: {parsed}")
        return parsed["result"]

    def send_message(self, chat_id: int, text: str) -> None:
        self.call("sendMessage", {"chat_id": chat_id, "text": text})

    def get_updates(self, offset: int | None = None, timeout: int = 30) -> list[dict]:
        payload: dict[str, int] = {"timeout": timeout}
        if offset is not None:
            payload["offset"] = offset
        return self.call("getUpdates", payload)

    def delete_webhook(self, drop_pending_updates: bool = False) -> None:
        self.call("deleteWebhook", {"drop_pending_updates": int(drop_pending_updates)})

    def get_me(self) -> dict:
        return self.call("getMe", {})


def admin_only(settings: Settings, user_id: int | None) -> bool:
    return bool(user_id and user_id in settings.admin_ids)


def _safe_full_name(user: dict) -> str:
    first = user.get("first_name") or ""
    last = user.get("last_name") or ""
    full = f"{first} {last}".strip()
    return full or "Unknown"


def _chat_title(chat: dict, user: dict) -> str:
    return str(chat.get("title") or _safe_full_name(user))


def handle_command(
    command_text: str,
    chat_id: int,
    user_id: int,
    tg: TelegramAPI,
    storage: Storage,
    settings: Settings,
) -> bool:
    if command_text.startswith("/start"):
        tg.send_message(
            chat_id,
            "Привет! Я бот автопарка. Пишите заявки на выходной, посадку на авто и любые рабочие вопросы.",
        )
        return True

    if command_text.startswith("/help"):
        is_admin = admin_only(settings, user_id)
        text = (
            "Команды:\n"
            "/start — подключить чат\n"
            "/help — помощь\n"
            "Просто отправьте сообщение для обработки."
        )
        if is_admin:
            text += "\n\nАдмин:\n/broadcast <текст>\n/chats"
        tg.send_message(chat_id, text)
        return True

    if command_text.startswith("/chats"):
        if not admin_only(settings, user_id):
            tg.send_message(chat_id, "Команда доступна только администратору.")
            return True
        chats = storage.list_chats()
        tg.send_message(chat_id, f"Подключено чатов: {len(chats)}\nID: {', '.join(map(str, chats))}")
        return True

    if command_text.startswith("/broadcast"):
        if not admin_only(settings, user_id):
            tg.send_message(chat_id, "Команда доступна только администратору.")
            return True

        parts = command_text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            tg.send_message(chat_id, "Использование: /broadcast <текст>")
            return True

        text = parts[1].strip()
        sent = 0
        failed = 0
        for target_chat in storage.list_chats():
            try:
                tg.send_message(target_chat, f"📢 Рассылка от диспетчера:\n\n{text}")
                sent += 1
            except Exception as exc:  # pragma: no cover
                failed += 1
                logger.warning("Failed broadcast to %s: %s", target_chat, exc)
        tg.send_message(chat_id, f"Рассылка завершена. Отправлено: {sent}, ошибок: {failed}")
        return True

    return False


def process_text_message(
    text: str,
    chat_id: int,
    user: dict,
    tg: TelegramAPI,
    storage: Storage,
    ai: AIClient,
    settings: Settings,
) -> None:
    history = storage.get_recent_chat_messages(chat_id)
    storage.add_chat_message(chat_id, "user", text)
    req_type, summary = ai.classify_driver_request(text)

    if req_type in {"day_off_request", "car_assignment_request"}:
        record = storage.save_request(
            user_id=int(user.get("id", 0)),
            full_name=_safe_full_name(user),
            username=user.get("username"),
            request_type=req_type,
            details=summary,
        )
        username_part = f" (@{record.username})" if record.username else ""
        admin_text = (
            "🚕 Новая заявка от водителя\n"
            f"Тип: {record.request_type}\n"
            f"Водитель: {record.full_name}{username_part}\n"
            f"ID: {record.user_id}\n"
            f"Детали: {record.details}\n"
            f"Время (UTC): {record.created_at}"
        )
        for admin_id in settings.admin_ids:
            try:
                tg.send_message(admin_id, admin_text)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed admin notification to %s: %s", admin_id, exc)

    reply = ai.assistant_reply(text, history=history)
    tg.send_message(chat_id, reply)
    storage.add_chat_message(chat_id, "assistant", reply)


def run(settings: Settings) -> None:
    storage = Storage(settings.db_path)
    ai = AIClient(
        gemini_api_key=settings.gemini_api_key,
        groq_api_key=settings.groq_api_key,
        model_name=settings.model_name,
    )
    tg = TelegramAPI(settings.telegram_token)

    tg.delete_webhook(drop_pending_updates=False)
    me = tg.get_me()
    logger.info("Connected as @%s (id=%s)", me.get("username"), me.get("id"))

    offset: int | None = None
    logger.info("Bot started in long-polling mode")

    while True:
        try:
            updates = tg.get_updates(offset=offset, timeout=25)
            for upd in updates:
                try:
                    offset = int(upd["update_id"]) + 1
                    message = upd.get("message") or upd.get("edited_message")
                    if not message:
                        continue

                    chat = message.get("chat", {})
                    user = message.get("from", {})
                    if "id" not in chat:
                        continue

                    chat_id = int(chat["id"])
                    user_id = int(user.get("id", 0))

                    storage.upsert_chat(
                        chat_id=chat_id,
                        title=_chat_title(chat, user),
                        chat_type=str(chat.get("type", "private")),
                    )

                    text = message.get("text")
                    if not text:
                        continue

                    if text.startswith("/") and handle_command(
                        command_text=text,
                        chat_id=chat_id,
                        user_id=user_id,
                        tg=tg,
                        storage=storage,
                        settings=settings,
                    ):
                        continue

                    process_text_message(
                        text=text,
                        chat_id=chat_id,
                        user=user,
                        tg=tg,
                        storage=storage,
                        ai=ai,
                        settings=settings,
                    )
                except Exception as exc:  # pragma: no cover
                    logger.exception("Failed to process update: %s", exc)

        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, RuntimeError) as exc:
            logger.warning("Loop error: %s", exc)
            time.sleep(3)
        except KeyboardInterrupt:
            logger.info("Bot stopped")
            return


def main() -> None:
    try:
        settings = load_settings()
    except ConfigError as exc:
        logger.error("Configuration error: %s", exc)
        return

    run(settings)


if __name__ == "__main__":
    main()
