import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from services.cleanup_service import cleanup_index_and_video_sync


class CleanupServiceTests(unittest.TestCase):
    def test_cleanup_only_deletes_old_date_video_folders(self):
        today = datetime.now().date()
        old_day = (today - timedelta(days=10)).strftime("%Y-%m-%d")
        recent_day = (today - timedelta(days=1)).strftime("%Y-%m-%d")

        with tempfile.TemporaryDirectory() as tmp:
            old_dir = os.path.join(tmp, old_day)
            recent_dir = os.path.join(tmp, recent_day)
            index_dir = os.path.join(tmp, "index")
            os.makedirs(old_dir)
            os.makedirs(recent_dir)
            os.makedirs(index_dir)

            with open(os.path.join(old_dir, "old.mkv"), "wb") as f:
                f.write(b"old")
            with open(os.path.join(recent_dir, "recent.mkv"), "wb") as f:
                f.write(b"recent")
            with open(os.path.join(index_dir, f"{old_day}.json"), "w", encoding="utf-8") as f:
                f.write("{}")

            with patch("services.cleanup_service.log"):
                stats = cleanup_index_and_video_sync(tmp, keep_days=3, enabled=True)

            self.assertFalse(os.path.exists(old_dir))
            self.assertTrue(os.path.exists(recent_dir))
            self.assertTrue(os.path.exists(index_dir))
            self.assertEqual(stats["deleted_folders"], 1)
            self.assertEqual(stats["failed"], 0)

    def test_disabled_cleanup_keeps_old_date_video_folders(self):
        old_day = (datetime.now().date() - timedelta(days=10)).strftime("%Y-%m-%d")

        with tempfile.TemporaryDirectory() as tmp:
            old_dir = os.path.join(tmp, old_day)
            os.makedirs(old_dir)

            with patch("services.cleanup_service.log"):
                stats = cleanup_index_and_video_sync(tmp, keep_days=3, enabled=False)

            self.assertTrue(os.path.exists(old_dir))
            self.assertEqual(stats["deleted_folders"], 0)


if __name__ == "__main__":
    unittest.main()
