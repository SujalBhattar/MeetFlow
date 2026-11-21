import sqlite3
import unittest
from pathlib import Path

from database import db
from tests.base import DatabaseTestCase


class DatabaseTests(DatabaseTestCase):

    def test_default_path_has_no_backslash(self):
        self.assertEqual(db.DEFAULT_DB_PATH, Path("data") / "meetflow.db")
        self.assertNotIn("\\", db.DEFAULT_DB_PATH.name)

    def test_schema_is_created_on_first_use(self):
        self.assertEqual(db.get_all_decisions(), [])
        self.assertEqual(db.get_all_actions(), [])
        self.assertTrue(db.DB_PATH.exists())

    def test_old_review_table_gets_new_columns(self):
        # Simulate a database made by the previous version.
        connection = sqlite3.connect(db.DB_PATH)
        connection.execute("""
            CREATE TABLE decision_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                old_decision_id INTEGER,
                new_decision TEXT,
                meeting_title TEXT,
                reason TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.commit()
        connection.close()

        db.initialize_database()

        with db.get_connection() as connection:
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(decision_reviews)"
                )
            }

        self.assertTrue(
            {"previous_decision", "speaker", "source_quote"} <= columns
        )

    def test_legacy_database_is_migrated_with_backups(self):
        legacy_dir = db.DB_PATH.parent / db.DB_PATH.stem
        legacy_dir.mkdir()
        legacy = legacy_dir / ".db"

        connection = sqlite3.connect(legacy)
        connection.execute(
            "CREATE TABLE decisions (id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " meeting_title TEXT, decision TEXT NOT NULL, speaker TEXT,"
            " source_quote TEXT, status TEXT DEFAULT 'active',"
            " created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "INSERT INTO decisions (decision) VALUES ('from legacy file')"
        )
        connection.commit()
        connection.close()

        # A different, older database already sits at the new path.
        stale = sqlite3.connect(db.DB_PATH)
        stale.execute("CREATE TABLE marker (note TEXT)")
        stale.execute("INSERT INTO marker VALUES ('from stale file')")
        stale.commit()
        stale.close()

        decisions = db.get_all_decisions()

        # The legacy data (the one Windows really used) wins...
        self.assertEqual(
            [row["decision"] for row in decisions], ["from legacy file"]
        )
        self.assertFalse(legacy.exists())

        # ...and the displaced database is kept as a backup.
        backup = db.DB_PATH.with_name("test.before-migration.db")
        self.assertTrue(backup.exists())

        kept = sqlite3.connect(backup)
        self.assertEqual(
            kept.execute("SELECT note FROM marker").fetchone()[0],
            "from stale file"
        )
        kept.close()

    def test_meeting_dedup(self):
        self.assertFalse(db.meeting_exists("hello"))
        db.record_meeting("Standup", "hello")
        self.assertTrue(db.meeting_exists("hello"))
        self.assertFalse(db.meeting_exists("something else"))

    def test_action_status_validation(self):
        action_id = db.save_action("M", "Write tests", "Sam")
        db.update_action_status(action_id, "completed")

        with self.assertRaises(ValueError):
            db.update_action_status(action_id, "banana")

        with self.assertRaises(ValueError):
            db.update_action_status(9999, "pending")

    def test_cannot_export_twice(self):
        action_id = db.save_action("M", "Ship it", "Sam")
        db.mark_action_exported(action_id, "card1", "http://x")

        with self.assertRaises(ValueError):
            db.mark_action_exported(action_id, "card2", "http://y")

    def test_owner_email_is_case_insensitive(self):
        db.save_owner_email("Sarah", "sarah@example.com")
        self.assertEqual(db.get_owner_email("sarah"), "sarah@example.com")
        self.assertTrue(db.delete_owner_email("SARAH"))
        self.assertIsNone(db.get_owner_email("Sarah"))


if __name__ == "__main__":
    unittest.main()
