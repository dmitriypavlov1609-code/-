from __future__ import annotations

import json
import re
import urllib.error
import urllib.request


class AIClient:
    def __init__(self, api_key: str | None, model_name: str) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self._api_url = "https://api.groq.com/openai/v1/chat/completions"

    def _post_chat(self, messages: list[dict[str, str]], temperature: float) -> str:
        if not self.api_key:
            raise urllib.error.URLError("GROQ_API_KEY is not configured")

        payload = {
            "model": self.model_name,
            "temperature": temperature,
            "messages": messages,
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self._api_url,
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
            "Ты живой диспетчер-ассистент автопарка. Отвечай на русском естественно, без шаблонов и без "
            "одинаковых фраз. Учитывай предыдущие сообщения чата. Не повторяй вопрос пользователя дословно. "
            "Если данных не хватает, задай 1-2 точных уточнения. "
            "Если это заявка на выходной, уточняй дату и смену. "
            "Если это заявка на машину или посадку, уточняй дату, смену, маршрут или парк, если этого не хватает. "
            "Если информации достаточно, коротко подтверди, что заявка принята, и скажи что будет передана диспетчеру. "
            "Пиши кратко: обычно 1-3 предложения."
        )
        try:
            messages = [{"role": "system", "content": prompt}]
            for item in history[-8:]:
                role = item.get("role", "user")
                content = item.get("text", "").strip()
                if role not in {"user", "assistant"} or not content:
                    continue
                messages.append({"role": role, "content": content[:1000]})
            messages.append({"role": "user", "content": message})
            reply = self._post_chat(
                messages=messages,
                temperature=0.7,
            )
            return reply.strip() or "Принял сообщение, передаю диспетчеру."
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, KeyError):
            text = message.lower()
            if re.search(r"(выходн|отгул|отпуск|не смогу)", text):
                return "Принял. Напишите, пожалуйста, на какую дату нужен выходной и какая у вас смена."
            if re.search(r"(посад|авто|машин|транспорт|смену на авто)", text):
                return "Принял. Уточните, пожалуйста, дату, смену и на какой маршрут или машину вас поставить."
            return "Принял сообщение. Если это заявка, напишите дату, смену и детали, чтобы я передал диспетчеру без задержки."
