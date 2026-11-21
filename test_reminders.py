import unittest
from datetime import date

from core.digest import generate_weekly_digests
from core.reminders import check_deadline_reminders
from database import db
from tests.base import DatabaseTestCase

TODAY = date(2026, 11, 21)


class Mailbox:
    """Stand-in for the Gmail sender."""

    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def __call__(self, recipient, subject, message):
        if self.fail:
            raise RuntimeError("SMTP down")
        self.sent.append((recipient, subject))


class ReminderTests(DatabaseTestCase):

    def setUp(self):
        super().setUp()
        db.save_action("M", "Overdue task", "Sarah", "2026-11-18")
        db.save_action("M", "Today task", "Sarah", "2026-11-21")
        db.save_action("M", "Soon task", "Alex", "November 23")
        db.save_action("M", "Far task", "Alex", "2026-12-25")
        db.save_action("M", "Vague task", "Alex", "after lunch")
        db.save_action("M", "No owner task", None, "2026-11-20")

        done_id = db.save_action("M", "Finished task", "Sarah", "2026-11-01")
        db.update_action_status(done_id, "completed")

        db.save_owner_email("Sarah", "sarah@example.com")

    def run_check(self, mailbox):
        return check_deadline_reminders(today=TODAY, send_email=mailbox)

    def test_buckets(self):
        results = self.run_check(Mailbox())

        self.assertEqual(len(results["overdue"]), 2)   # incl. no-owner
        self.assertEqual(len(results["due_today"]), 1)
        self.assertEqual(len(results["upcoming"]), 1)
        self.assertEqual(results["skipped"], ["Vague task"])

    def test_completed_and_far_tasks_are_ignored(self):
        self.run_check(Mailbox())
        tasks = {row["task"] for row in db.get_all_reminders()}

        self.assertNotIn("Finished task", tasks)
        self.assertNotIn("Far task", tasks)

    def test_emails_go_only_to_registered_owners(self):
        mailbox = Mailbox()
        results = self.run_check(mailbox)

        self.assertEqual(len(mailbox.sent), 2)  # Sarah: overdue + today
        self.assertTrue(
            all(to == "sarah@example.com" for to, _ in mailbox.sent)
        )

        reasons = {item["task"]: item["reason"]
                   for item in results["email_skipped"]}
        self.assertIn("Soon task", reasons)      # Alex has no address
        self.assertIn("No owner task", reasons)

    def test_second_check_creates_and_sends_nothing(self):
        self.run_check(Mailbox())
        mailbox = Mailbox()
        results = self.run_check(mailbox)

        self.assertEqual(results["overdue"], [])
        self.assertEqual(mailbox.sent, [])

    def test_failed_email_is_retried_next_time(self):
        failed = self.run_check(Mailbox(fail=True))
        self.assertEqual(len(failed["email_failed"]), 2)

        retry_box = Mailbox()
        retried = self.run_check(retry_box)

        self.assertEqual(len(retry_box.sent), 2)
        self.assertEqual(retried["email_failed"], [])

    def test_address_added_later_still_gets_the_email(self):
        self.run_check(Mailbox())
        db.save_owner_email("Alex", "alex@example.com")

        mailbox = Mailbox()
        self.run_check(mailbox)

        self.assertEqual(
            [to for to, _ in mailbox.sent], ["alex@example.com"]
        )


class DigestTests(DatabaseTestCase):

    def test_digest_groups_by_owner_and_ignores_superseded(self):
        db.save_action("M", "Build API", "Alex", "2026-01-01")
        old_id = db.save_decision("M", "Old plan", "Alex")
        db.save_decision("M", "Current plan", "Alex")

        with db.get_connection() as connection:
            connection.execute(
                "UPDATE decisions SET status='superseded' WHERE id=?",
                (old_id,)
            )

        digest = generate_weekly_digests()
        alex = digest["people"]["Alex"]

        self.assertEqual(len(alex["tasks"]), 1)
        self.assertEqual(len(alex["overdue"]), 1)
        self.assertEqual(
            [d["decision"] for d in alex["decisions"]], ["Current plan"]
        )


if __name__ == "__main__":
    unittest.main()
