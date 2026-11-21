import unittest
from types import SimpleNamespace

from core import approval
from core.validation import filter_findings
from database import db
from tests.base import DatabaseTestCase


def conflict(previous_id, previous_text, new_text):
    return SimpleNamespace(
        status="conflict",
        previous_decision_id=previous_id,
        previous_decision=previous_text,
        new_decision=new_text,
        reason="Date changed",
    )


def new_decision(text, speaker="Alex", quote="Let's move it."):
    return SimpleNamespace(
        description=text, speaker=speaker, source_quote=quote
    )


class ApprovalFlowTests(DatabaseTestCase):

    def setUp(self):
        super().setUp()
        self.old_id = db.save_decision(
            "Planning", "Launch on December 5", "Sarah", "Launch Dec 5"
        )
        self.report = SimpleNamespace(findings=[
            conflict(
                self.old_id,
                "Launch on December 5",
                "Launch on December 10"
            ),
            SimpleNamespace(
                status="same_decision",
                previous_decision_id=self.old_id,
                previous_decision="x",
                new_decision="y",
                reason="same",
            ),
        ])
        self.decisions = [new_decision("Launch on December 10")]

    def queue(self):
        return approval.create_pending_reviews(
            self.report, self.decisions, "Replanning"
        )

    def test_only_conflicts_are_queued_and_keep_their_details(self):
        ids = self.queue()
        reviews = approval.get_reviews()

        self.assertEqual(len(ids), 1)
        self.assertEqual(len(reviews), 1)
        self.assertEqual(
            reviews[0]["previous_decision"], "Launch on December 5"
        )
        self.assertEqual(reviews[0]["speaker"], "Alex")
        self.assertEqual(reviews[0]["source_quote"], "Let's move it.")
        self.assertEqual(reviews[0]["meeting_title"], "Replanning")

    def test_same_conflict_is_not_queued_twice(self):
        self.queue()
        self.queue()
        self.assertEqual(len(approval.get_reviews()), 1)

    def test_approve_replaces_the_old_decision(self):
        review_id = self.queue()[0]
        approval.approve_review(review_id)

        active = [row["decision"] for row in db.get_active_decisions()]
        self.assertEqual(active, ["Launch on December 10"])

        history = {row["id"]: row for row in db.get_all_decisions()}
        self.assertEqual(history[self.old_id]["status"], "superseded")
        self.assertEqual(approval.get_reviews(), [])

        new_row = db.get_active_decisions()[0]
        self.assertEqual(new_row["speaker"], "Alex")
        self.assertEqual(new_row["meeting_title"], "Replanning")

    def test_reject_keeps_the_old_decision(self):
        review_id = self.queue()[0]
        approval.reject_review(review_id)

        active = [row["decision"] for row in db.get_active_decisions()]
        self.assertEqual(active, ["Launch on December 5"])
        self.assertEqual(approval.get_reviews(), [])

    def test_a_review_can_only_be_resolved_once(self):
        review_id = self.queue()[0]
        approval.approve_review(review_id)

        with self.assertRaises(ValueError):
            approval.approve_review(review_id)

        with self.assertRaises(ValueError):
            approval.reject_review(review_id)

    def test_unknown_review_raises(self):
        with self.assertRaises(ValueError):
            approval.approve_review(12345)


class FilterFindingsTests(unittest.TestCase):

    def test_invented_ids_are_dropped_and_text_is_corrected(self):
        real = conflict(1, "model rewrote this", "New plan")
        invented = conflict(99, "ghost", "New plan")
        duplicate = conflict(1, "again", "New plan")

        kept = filter_findings(
            [real, invented, duplicate], {1: "Stored text"}
        )

        self.assertEqual(kept, [real])
        self.assertEqual(real.previous_decision, "Stored text")


if __name__ == "__main__":
    unittest.main()
