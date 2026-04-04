from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from difflib import SequenceMatcher


class AIClient:
    def __init__(
        self,
        api_key: str | None = None,
        api_url: str = "https://api.cometapi.com/v1/chat/completions",
        model_name: str = "gpt-5",
        openai_api_key: str | None = None,
        embedding_model: str = "text-embedding-3-small",
    ) -> None:
        self.api_key = api_key
        self.api_url = api_url
        self.model_name = model_name
        self.search_model_name = "gpt-5-search-api"
        self.openai_api_key = openai_api_key or api_key
        self.embedding_model = embedding_model

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())

    def _is_model_question(self, message: str) -> bool:
        text = self._normalize_text(message)
        patterns = [
            r"на какой модели",
            r"какая модель",
            r"какой ии",
            r"на чем ты работа",
            r"на ч[её]м ты работа",
            r"какой у тебя gpt",
            r"ты gpt[- ]?4",
            r"ты gpt[- ]?5",
        ]
        return any(re.search(pattern, text) for pattern in patterns)

    def _general_fallback_reply(self, message: str, history: list[dict[str, str]] | None = None) -> str:
        history = history or []
        assistant_history = [
            item.get("text", "").strip()
            for item in history
            if item.get("role") == "assistant" and item.get("text", "").strip()
        ]
        variants = [
            "Понял вопрос. Уточните чуть подробнее, и я отвечу по существу.",
            "Запрос получил. Если добавите деталей, смогу ответить точнее.",
            "Принял. Сформулируйте задачу чуть конкретнее, чтобы дать точный ответ.",
            "Хорошо. Если нужен предметный ответ, добавьте контекст или уточняющие детали.",
        ]
        recent_normalized = {self._normalize_text(item) for item in assistant_history[-4:]}
        for variant in variants:
            if self._normalize_text(variant) not in recent_normalized:
                return variant
        return variants[0]

    def _looks_repetitive(self, reply: str, history: list[dict[str, str]]) -> bool:
        normalized_reply = self._normalize_text(reply)
        if not normalized_reply:
            return True

        recent_assistant = [
            self._normalize_text(item.get("text", ""))
            for item in history[-4:]
            if item.get("role") == "assistant" and item.get("text", "").strip()
        ]
        if not recent_assistant:
            return False

        for previous in recent_assistant:
            if normalized_reply == previous:
                return True
            if SequenceMatcher(None, normalized_reply, previous).ratio() >= 0.9:
                return True
        return False

    def _fallback_reply(self, message: str, history: list[dict[str, str]] | None = None) -> str:
        history = history or []
        text = message.lower()
        if self._is_model_question(message):
            return "Бот работает через CometAPI, текущая модель настроена как gpt-5."
        assistant_history = [
            item.get("text", "").strip()
            for item in history
            if item.get("role") == "assistant" and item.get("text", "").strip()
        ]

        if re.search(r"(выходн|отгул|отпуск|не смогу)", text):
            variants = [
                "Заявку принял. Укажите дату выходного и вашу смену.",
                "Информацию получил. Уточните, пожалуйста, число и смену.",
                "Принято. Для передачи диспетчеру нужны дата выходного и смена.",
                "Запрос зафиксирован. Напишите дату и смену.",
            ]
        elif re.search(r"(посад|авто|машин|транспорт|смену на авто)", text):
            variants = [
                "Запрос принят. Уточните дату, смену и маршрут либо машину.",
                "Информацию получил. Нужны дата, смена и место постановки.",
                "Принято. Напишите дату, смену и маршрут или номер машины.",
                "Зафиксировал запрос. Укажите дату, смену и куда вас поставить.",
            ]
        else:
            return self._general_fallback_reply(message, history=history)

        recent_normalized = {self._normalize_text(item) for item in assistant_history[-4:]}
        for variant in variants:
            if self._normalize_text(variant) not in recent_normalized:
                return variant

        index = int(hashlib.sha256(message.encode("utf-8")).hexdigest(), 16) % len(variants)
        return variants[index]

    def _post_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        model_name: str | None = None,
    ) -> str:
        if not self.api_key:
            raise urllib.error.URLError("No LLM API key is configured")

        payload = {
            "model": model_name or self.model_name,
            "temperature": temperature,
            "messages": messages,
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.api_url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
        return parsed["choices"][0]["message"]["content"]

    def _should_search_web(self, message: str) -> bool:
        text = message.lower().strip()
        patterns = [
            r"\bпогода\b",
            r"\bновост",
            r"\bкурс\b",
            r"\bцена\b",
            r"\bстоимост",
            r"\bсколько стоит\b",
            r"\bчто нового\b",
            r"\bсегодня\b",
            r"\bсейчас\b",
            r"\bна этой неделе\b",
            r"\bпоследн",
            r"\bсвеж",
            r"\bнайди\b",
            r"\bзагугли\b",
            r"\bпоищи\b",
            r"\bпосмотри в интернете\b",
            r"\bкто сейчас\b",
            r"\bкакой сейчас\b",
            r"\bактуальн",
            r"\bадрес\b",
            r"\bчасы работы\b",
            r"\bсайт\b",
            r"\bотзывы\b",
            r"\bрейтинг\b",
        ]
        return any(re.search(pattern, text) for pattern in patterns)

    def _heuristic_classification(self, message: str) -> tuple[str, str]:
        text = message.lower()
        if re.search(r"(выходн|отгул|не смогу|отпуск)", text):
            return "day_off_request", message[:140]
        if re.search(r"(посад|авто|машин|транспорт|смену на авто)", text):
            return "car_assignment_request", message[:140]
        return "general_message", message[:140]

    def classify_driver_request(self, message: str) -> tuple[str, str]:
        prompt = (
            "Ты диспетчер автопарка. Классифицируй сообщение водителя ровно в один тип: "
            "day_off_request, car_assignment_request, general_message. "
            "summary должен быть коротким, конкретным и по-русски. "
            "Ответь только JSON: {\"type\":\"...\",\"summary\":\"...\"}."
        )

        try:
            reply = self._post_chat(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": message},
                ],
                temperature=0.1,
            )
            data = json.loads(reply)
            req_type = str(data.get("type", "general_message"))
            summary = str(data.get("summary", message[:140]))[:140]
            if req_type not in {"day_off_request", "car_assignment_request", "general_message"}:
                req_type = "general_message"
            return req_type, summary
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, KeyError):
            return self._heuristic_classification(message)

    def assistant_reply(self, message: str, history: list[dict[str, str]] | None = None) -> str:
        history = history or []
        if self._is_model_question(message):
            return "Бот работает через CometAPI, текущая модель настроена как gpt-5."

        prompt = (
            "Ты полезный русскоязычный ассистент для водителей и диспетчерских задач. "
            "Отвечай по существу, естественно и уверенно. Будь общительным, но не многословным. "
            "Сначала пытайся понять обычный человеческий вопрос и дать нормальный ответ, а не сводить всё к заявкам. "
            "Учитывай предыдущие сообщения чата и опирайся на контекст разговора. "
            "Если вопрос общий, отвечай как обычный компетентный ассистент. "
            "Если это рабочая заявка на выходной, смену, маршрут, авто или постановку, отвечай как диспетчер-ассистент: кратко подтверди, что запрос принят, и при необходимости уточни недостающие детали. "
            "Если данных недостаточно, задай 1-2 точных уточнения. "
            "Не повторяй вопрос пользователя дословно. Не выдумывай факты. "
            "Если вопрос требует актуальной информации из интернета, используй веб-поиск и отвечай по найденным данным. "
            "Если пользователь спрашивает, на какой модели работает бот, отвечай ровно: 'Бот работает через CometAPI, текущая модель настроена как gpt-5.' "
            "Чередуй формулировки и не используй одну и ту же конструкцию подряд. "
            "Пиши обычно 2-5 предложений, если ситуация не требует короче."
        )
        try:
            messages = [{"role": "system", "content": prompt}]
            for item in history[-16:]:
                role = item.get("role", "user")
                content = item.get("text", "").strip()
                if role not in {"user", "assistant"} or not content:
                    continue
                messages.append({"role": role, "content": content[:1000]})
            messages.append({"role": "user", "content": message})
            target_model = self.search_model_name if self._should_search_web(message) else self.model_name
            try:
                reply = self._post_chat(
                    messages=messages,
                    temperature=0.7,
                    model_name=target_model,
                )
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, KeyError):
                reply = self._post_chat(
                    messages=messages,
                    temperature=0.7,
                    model_name=self.model_name,
                )
            cleaned_reply = reply.strip() or "Принял сообщение, передаю диспетчеру."
            if self._looks_repetitive(cleaned_reply, history):
                rewrite_prompt = (
                    "Переформулируй ответ по-русски заметно иначе в деловом стиле. "
                    "Сохрани смысл, но измени структуру фраз, начало, лексику и форму подтверждения. "
                    "Не делай ответ длиннее 3 предложений."
                )
                rewrite_messages = messages + [
                    {"role": "assistant", "content": cleaned_reply},
                    {"role": "user", "content": rewrite_prompt},
                ]
                rewritten = self._post_chat(
                    rewrite_messages,
                    temperature=1.0,
                    model_name=target_model,
                ).strip()
                if rewritten and not self._looks_repetitive(rewritten, history):
                    return rewritten
                return self._fallback_reply(message, history=history)
            return cleaned_reply
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, KeyError):
            return self._fallback_reply(message, history=history)

    # ========================================================================
    # Embeddings Methods (for RAG)
    # ========================================================================

    def get_embedding(self, text: str) -> list[float]:
        """
        Get embedding vector from OpenAI API.

        Args:
            text: Text to embed

        Returns:
            List of floats (1536 dimensions for text-embedding-3-small)

        Raises:
            ValueError: If OpenAI API key is not configured
            urllib.error.URLError: If API request fails
        """
        if not self.openai_api_key:
            raise ValueError("OpenAI API key required for embeddings")

        payload = {
            "model": self.embedding_model,
            "input": text[:8000],  # Truncate to avoid token limits
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=data,
            headers={
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            parsed = json.loads(response.read().decode("utf-8"))

        return parsed["data"][0]["embedding"]

    def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Get embeddings for multiple texts in a single API call (more efficient).

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            ValueError: If OpenAI API key is not configured
            urllib.error.URLError: If API request fails
        """
        if not self.openai_api_key:
            raise ValueError("OpenAI API key required for embeddings")

        # Truncate texts and limit batch size
        truncated_texts = [text[:8000] for text in texts[:100]]

        payload = {
            "model": self.embedding_model,
            "input": truncated_texts,
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=data,
            headers={
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=60) as response:
            parsed = json.loads(response.read().decode("utf-8"))

        # Sort by index to maintain order
        embeddings_data = sorted(parsed["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in embeddings_data]
