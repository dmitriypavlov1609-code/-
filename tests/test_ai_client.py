import unittest

from bot.ai_client import AIClient


class AIClientFallbackTests(unittest.TestCase):
    def test_day_off_heuristic(self) -> None:
        ai = AIClient(api_key=None, model_name="mock")
        req_type, summary = ai.classify_driver_request("Нужен выходной в воскресенье")
        self.assertEqual(req_type, "day_off_request")
        self.assertIn("выходной", summary.lower())

    def test_car_assignment_heuristic(self) -> None:
        ai = AIClient(api_key=None, model_name="mock")
        req_type, _ = ai.classify_driver_request("Прошу посадить меня на авто завтра")
        self.assertEqual(req_type, "car_assignment_request")

    def test_fallback_reply_avoids_recent_duplicate(self) -> None:
        ai = AIClient(api_key=None, model_name="mock")
        history = [
            {
                "role": "assistant",
                "text": "Принял. Напишите, пожалуйста, дату выходного и вашу смену.",
            }
        ]
        reply = ai.assistant_reply("Мне нужен выходной", history=history)
        self.assertNotEqual(
            reply,
            "Принял. Напишите, пожалуйста, дату выходного и вашу смену.",
        )

    def test_detects_web_search_queries(self) -> None:
        ai = AIClient(api_key=None, model_name="mock")
        self.assertTrue(ai._should_search_web("Найди свежие новости по такси в Москве"))
        self.assertTrue(ai._should_search_web("Какая сейчас погода в Казани?"))
        self.assertFalse(ai._should_search_web("Мне нужен выходной на завтра"))

    def test_model_question_returns_fixed_answer(self) -> None:
        ai = AIClient(api_key=None, model_name="mock")
        reply = ai.assistant_reply("На какой модели ты работаешь?")
        self.assertEqual(
            reply,
            "Бот работает через CometAPI, текущая модель настроена как gpt-5.",
        )

    def test_general_fallback_is_not_dispatch_only(self) -> None:
        ai = AIClient(api_key=None, model_name="mock")
        reply = ai.assistant_reply("Объясни простыми словами, что такое инфляция")
        self.assertNotIn("заявк", reply.lower())
        self.assertNotIn("смен", reply.lower())


if __name__ == "__main__":
    unittest.main()
