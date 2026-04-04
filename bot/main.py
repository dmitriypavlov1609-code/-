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
            if storage.use_postgres:
                text += (
                    "\n\nПрофили водителей:\n"
                    "/driver_info <user_id> — информация о водителе\n"
                    "/driver_stats <user_id> — статистика водителя\n"
                    "/set_driver_pref <user_id> <key> <value> — установить настройку"
                )
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

    # Driver profile commands (PostgreSQL only)
    if storage.use_postgres:
        if command_text.startswith("/driver_info"):
            if not admin_only(settings, user_id):
                tg.send_message(chat_id, "Команда доступна только администратору.")
                return True

            parts = command_text.split(maxsplit=1)
            if len(parts) < 2:
                tg.send_message(chat_id, "Использование: /driver_info <user_id>")
                return True

            try:
                target_user_id = int(parts[1])
                from .driver_profile import DriverProfileManager, format_driver_info

                manager = DriverProfileManager(storage)
                profile = storage.get_or_create_driver_profile(target_user_id, {"full_name": "Unknown"})
                stats = manager.get_stats_summary(target_user_id)
                preferences = manager.get_preferences(target_user_id)

                info = format_driver_info(profile, stats, preferences)
                tg.send_message(chat_id, info)
            except ValueError:
                tg.send_message(chat_id, "Неверный формат user_id. Используйте число.")
            except Exception as exc:
                logger.error(f"Failed to get driver info: {exc}")
                tg.send_message(chat_id, f"Ошибка: {exc}")
            return True

        if command_text.startswith("/set_driver_pref"):
            if not admin_only(settings, user_id):
                tg.send_message(chat_id, "Команда доступна только администратору.")
                return True

            parts = command_text.split(maxsplit=3)
            if len(parts) < 4:
                tg.send_message(
                    chat_id,
                    "Использование: /set_driver_pref <user_id> <key> <value>\n"
                    "Пример: /set_driver_pref 123456789 shift_preference morning"
                )
                return True

            try:
                target_user_id = int(parts[1])
                pref_key = parts[2]
                pref_value = parts[3]

                from .driver_profile import DriverProfileManager
                manager = DriverProfileManager(storage)
                manager.set_preference(target_user_id, pref_key, pref_value)

                tg.send_message(chat_id, f"✓ Настройка установлена: {pref_key}={pref_value}")
            except ValueError:
                tg.send_message(chat_id, "Неверный формат user_id. Используйте число.")
            except Exception as exc:
                logger.error(f"Failed to set preference: {exc}")
                tg.send_message(chat_id, f"Ошибка: {exc}")
            return True

        if command_text.startswith("/driver_stats"):
            if not admin_only(settings, user_id):
                tg.send_message(chat_id, "Команда доступна только администратору.")
                return True

            parts = command_text.split(maxsplit=1)
            if len(parts) < 2:
                tg.send_message(chat_id, "Использование: /driver_stats <user_id>")
                return True

            try:
                target_user_id = int(parts[1])
                from .driver_profile import DriverProfileManager

                manager = DriverProfileManager(storage)
                stats = manager.get_stats_summary(target_user_id, days=30)

                stats_text = (
                    f"📊 Статистика водителя {target_user_id} (30 дней)\n\n"
                    f"Всего сообщений: {stats.get('total_messages', 0)}\n"
                    f"Всего заявок: {stats.get('total_requests', 0)}\n"
                    f"- Выходные: {stats.get('day_off_requests', 0)}\n"
                    f"- Постановка на авто: {stats.get('car_assignment_requests', 0)}\n"
                    f"Активных дней: {stats.get('active_days', 0)}"
                )
                tg.send_message(chat_id, stats_text)
            except ValueError:
                tg.send_message(chat_id, "Неверный формат user_id. Используйте число.")
            except Exception as exc:
                logger.error(f"Failed to get driver stats: {exc}")
                tg.send_message(chat_id, f"Ошибка: {exc}")
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
    # Get or create driver profile (if PostgreSQL is enabled)
    driver_profile = None
    profile_manager = None
    if storage.use_postgres:
        try:
            from .driver_profile import DriverProfileManager
            profile_manager = DriverProfileManager(storage)

            driver_profile = storage.get_or_create_driver_profile(
                user_id=int(user.get("id", 0)),
                user_data={
                    "full_name": _safe_full_name(user),
                    "username": user.get("username"),
                }
            )

            # Update activity
            profile_manager.update_activity(int(user.get("id", 0)))

        except Exception as exc:
            logger.warning(f"Failed to get/create driver profile: {exc}")

    history = storage.get_recent_chat_messages(chat_id)
    message_id = storage.add_chat_message(chat_id, "user", text)

    # Classify request
    req_type, summary = ai.classify_driver_request(text)

    # Save request if needed
    if req_type in {"day_off_request", "car_assignment_request"}:
        record = storage.save_request(
            user_id=int(user.get("id", 0)),
            full_name=_safe_full_name(user),
            username=user.get("username"),
            request_type=req_type,
            details=summary,
        )

        # Track request in statistics
        if profile_manager:
            try:
                profile_manager.track_request(int(user.get("id", 0)), req_type)
            except Exception as exc:
                logger.debug(f"Failed to track request: {exc}")

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

    # Generate reply with RAG if enabled
    if settings.rag_enabled and storage.use_postgres:
        try:
            from .rag import RAGPipeline
            rag = RAGPipeline(storage, ai, top_k=settings.rag_top_k)

            # Use RAG for appropriate queries
            if rag.should_use_rag(text):
                reply, citations = rag.generate_answer(
                    query=text,
                    history=history,
                    driver_profile=driver_profile,
                )
                logger.info(f"RAG reply generated with {len(citations)} citations")
            else:
                # Fallback to regular assistant reply
                reply = ai.assistant_reply(text, history=history)
        except Exception as exc:
            logger.error(f"RAG generation failed: {exc}")
            # Fallback to regular assistant reply
            reply = ai.assistant_reply(text, history=history)
    else:
        # Regular assistant reply (no RAG)
        reply = ai.assistant_reply(text, history=history)

    tg.send_message(chat_id, reply)
    storage.add_chat_message(chat_id, "assistant", reply)

    # Store message embedding in background (optional, best effort)
    if storage.use_postgres and settings.rag_enabled:
        try:
            embedding = ai.get_embedding(text)
            storage.add_message_embedding(message_id, embedding)
        except Exception as exc:
            logger.debug(f"Failed to store message embedding: {exc}")


def run(settings: Settings) -> None:
    storage = Storage(
        db_path=settings.db_path,
        postgres_url=settings.postgres_url,
        use_postgres=settings.use_postgres,
    )
    ai = AIClient(
        api_key=settings.llm_api_key,
        api_url=settings.llm_api_url,
        model_name=settings.model_name,
        openai_api_key=settings.openai_api_key,
        embedding_model=settings.embedding_model,
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
