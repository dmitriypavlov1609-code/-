import os
import unittest

from bot.config import ConfigError, load_settings


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_backup = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_load_settings_requires_telegram_token(self) -> None:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        with self.assertRaises(ConfigError):
            load_settings()

    def test_load_settings_parses_admin_ids(self) -> None:
        os.environ["TELEGRAM_BOT_TOKEN"] = "token"
        os.environ["ADMIN_IDS"] = "1, 2,3"
        settings = load_settings()
        self.assertEqual(settings.admin_ids, {1, 2, 3})


if __name__ == "__main__":
    unittest.main()
