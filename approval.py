from database.db import (
    create_review,
    get_pending_reviews,
    resolve_review
)


def create_pending_reviews(report, new_decisions, meeting_title=None):
    """Queue every detected conflict for human approval."""

    decisions_by_text = {
        decision.description: decision
        for decision in new_decisions
    }

    created_ids = []

    for finding in report.findings:

        if finding.status != "conflict":
            continue

        matching_decision = decisions_by_text.get(finding.new_decision)

        review_id = create_review(
            previous_id=finding.previous_decision_id,
            previous_decision=finding.previous_decision,
            new_decision=finding.new_decision,
            reason=finding.reason,
            meeting_title=meeting_title,
            speaker=(
                matching_decision.speaker if matching_decision else None
            ),
            source_quote=(
                matching_decision.source_quote
                if matching_decision else None
            )
        )

        created_ids.append(review_id)

    return created_ids


def get_reviews():
    return get_pending_reviews()


def approve_review(review_id):
    """Replace the old decision with the proposed one."""
    return resolve_review(review_id, "approved")


def reject_review(review_id):
    """Keep the old decision and discard the proposal."""
    return resolve_review(review_id, "rejected")
