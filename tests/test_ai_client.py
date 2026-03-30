import unittest

from bot.ai_client import AIClient


class AIClientFallbackTests(unittest.TestCase):
    def test_day_off_heuristic(self) -> None:
        ai = AIClient(gemini_api_key=None, groq_api_key=None, model_name="mock")
        req_type, summary = ai.classify_driver_request("Нужен выходной в воскресенье")
        self.assertEqual(req_type, "day_off_request")
        self.assertIn("выходной", summary.lower())

    def test_car_assignment_heuristic(self) -> None:
        ai = AIClient(gemini_api_key=None, groq_api_key=None, model_name="mock")
        req_type, _ = ai.classify_driver_request("Прошу посадить меня на авто завтра")
        self.assertEqual(req_type, "car_assignment_request")


if __name__ == "__main__":
    unittest.main()
