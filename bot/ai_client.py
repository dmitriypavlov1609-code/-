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
    ) -> None:
        self.api_key = api_key
        self.api_url = api_url
        self.model_name = model_name
        self.search_model_name = "gpt-5-search-api"

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())

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
            variants = [
                "Сообщение получил. Если это заявка, направьте дату, смену и детали.",
                "Информацию принял. При необходимости оформления заявки добавьте дату и подробности.",
                "Запрос получен. Если вопрос касается смены или машины, уточните дату и детали.",
                "Принято к работе. Если требуется оформление заявки, укажите дату, смену и суть вопроса.",
            ]

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
        prompt = (
            "Ты диспетчер-ассистент автопарка. Отвечай на русском в деловом, уверенном и естественном стиле. "
            "Будь более общительным: поддерживай ход разговора, отвечай не сухо, но без пустой болтовни. "
            "Не используй разговорные штампы, лишнюю воду и повторяющиеся начала фраз. "
            "Учитывай предыдущие сообщения чата и опирайся на контекст разговора, а не только на последнюю реплику. "
            "Не повторяй вопрос пользователя дословно. "
            "Если данных не хватает, задай 1-2 точных уточнения. "
            "Если это заявка на выходной, уточняй дату и смену. "
            "Если это заявка на машину или посадку, уточняй дату, смену, маршрут, парк или номер машины, если этого не хватает. "
            "Если информации достаточно, кратко подтверди принятие заявки и укажи, что она будет передана диспетчеру. "
            "Чередуй формулировки: используй разные деловые конструкции вроде 'принято', 'зафиксировал', 'информацию получил', 'заявка принята', но не повторяй одну и ту же форму подряд. "
            "Если пользователь спрашивает, на какой модели работает бот, отвечай: 'Бот работает через CometAPI, текущая модель настроена как gpt-5.' "
            "Если вопрос требует актуальной информации из интернета, используй веб-поиск и отвечай по найденным данным. "
            "Пиши обычно 2-5 предложений, если ситуация не требует короче. "
            "Если твой последний ответ в истории был похож по смыслу, сформулируй новый ответ заметно иначе."
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
            reply = self._post_chat(
                messages=messages,
                temperature=0.7,
                model_name=target_model,
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
