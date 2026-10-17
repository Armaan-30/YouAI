import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from app.storage import Store
from app import tasks

class TaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "tasks.db")
        self.now = datetime(2026, 10, 16, 21, 30, tzinfo=tasks.ZONE)

    def run_task(self, text, key="request-1"):
        return tasks.execute(text, key, self.store, self.now)

    def test_relative_reminder_is_persisted_and_retry_is_idempotent(self):
        text = "Remind me in ten minutes to drink water"
        first = self.run_task(text)
        self.assertEqual(first, self.run_task(text))
        items = self.store.reminders()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["due_at"], self.now.timestamp() + 600)
        self.assertEqual(items[0]["content"], "drink water")
        self.assertIn("Keep YouAI open", first)

    def test_timer_cancel_and_restart(self):
        self.run_task("Set a timer for 5 minutes")
        reopened = Store(self.store.path)
        self.assertEqual(len(reopened.reminders()), 1)
        self.assertIn("Cancelled", self.run_task("Cancel timer 1", "cancel"))
        self.assertEqual(reopened.reminders(), [])

    def test_note_search_and_read_use_saved_content(self):
        self.run_task("Save a note: groceries are apples")
        self.run_task("Save a note: book a train", "request-2")
        self.assertIn("apples", self.run_task("Find notes about groceries", "search"))
        self.assertNotIn("train", self.run_task("Find notes about groceries", "search"))
        self.assertIn("train", self.run_task("Read my notes", "read"))

    def test_ambiguous_invalid_and_past_times_do_not_schedule(self):
        for text in ("Remind me tomorrow at 9 to call Sam",
                     "Remind me today at 9 AM to call Sam",
                     "Remind me tomorrow at 25:00 to call Sam",
                     "Set a timer for 0 minutes", "Remind me later to call Sam"):
            self.assertIsNotNone(self.run_task(text))
        self.assertEqual(self.store.reminders(), [])

    def test_tomorrow_uses_configured_timezone(self):
        self.run_task("Remind me tomorrow at 9 AM to call Sam")
        expected = datetime(2026, 10, 17, 9, tzinfo=tasks.ZONE).timestamp()
        self.assertEqual(self.store.reminders()[0]["due_at"], expected)

    def test_request_id_cannot_be_reused_for_another_action(self):
        self.run_task("Save a note: first")
        with self.assertRaises(ValueError):
            self.run_task("Save a note: second")
        self.assertEqual(len(self.store.notes()), 1)

    def test_unrelated_question_does_not_execute_anything(self):
        self.assertIsNone(self.run_task("What are reminders?"))
        self.assertEqual(self.store.reminders(), [])
