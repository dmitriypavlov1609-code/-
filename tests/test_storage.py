import tempfile
import unittest
from pathlib import Path

from bot.storage import Storage


class StorageTests(unittest.TestCase):
    def test_upsert_list_and_save_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.sqlite3"
            storage = Storage(str(db_path))

            storage.upsert_chat(100, "Chat A", "private")
            storage.upsert_chat(101, "Chat B", "group")
            self.assertEqual(sorted(storage.list_chats()), [100, 101])

            record = storage.save_request(
                user_id=55,
                full_name="Test Driver",
                username="driver",
                request_type="day_off_request",
                details="выходной завтра",
            )
            self.assertEqual(record.user_id, 55)
            self.assertEqual(record.request_type, "day_off_request")


if __name__ == "__main__":
    unittest.main()
