
from database.db import (
    create_review,
    get_pending_reviews,
    resolve_review
)


def create_pending_reviews(report, new_decisions):

    created_ids = []

    for finding in report.findings:

        if finding.status != "conflict":
            continue

        matching_decision = next(
            (
                decision
                for decision in new_decisions
                if decision.description == finding.new_decision
            ),
            None
        )

        speaker = (
            matching_decision.speaker
            if matching_decision else None
        )

        source_quote = (
            matching_decision.source_quote
            if matching_decision else None
        )

        review_id = create_review(
            previous_id=finding.previous_decision_id,
            previous_decision=finding.previous_decision,
            new_decision=finding.new_decision,
            reason=finding.reason,
            speaker=speaker,
            source_quote=source_quote
        )

        created_ids.append(review_id)

    return created_ids


def get_reviews():
    return get_pending_reviews()


def approve_review(review_id):
    return resolve_review(review_id, approved=True)


def reject_review(review_id):
    return resolve_review(review_id, approved=False)
