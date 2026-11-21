
from pathlib import Path

from core.extractor import extract_meeting
from core.conflict import detect_conflicts
from core.approval import (
    create_pending_reviews,
    get_reviews,
    approve_review,
    reject_review
)


transcript = Path(
    "sample_data/meeting_02.txt"
).read_text(encoding="utf-8")

print("\nMEETFLOW: ANALYZING MEETING...\n")

extraction = extract_meeting(transcript)

report = detect_conflicts(extraction.decisions)

create_pending_reviews(
    report,
    extraction.decisions
)

reviews = get_reviews()

print("=" * 55)
print("MEETFLOW: PENDING APPROVALS")
print("=" * 55)

if not reviews:
    print("\nNo pending approvals.")
    raise SystemExit

for review in reviews:

    print(f"\nReview ID: {review['id']}")
    print(f"Previous: {review['previous_decision']}")
    print(f"Proposed: {review['new_decision']}")
    print(f"Reason: {review['reason']}")

    print("\nWhat should MeetFlow do?")
    print("[A] Approve change")
    print("[R] Reject change")

    choice = input("\nYour choice: ").strip().lower()

    if choice == "a":

        result = approve_review(review["id"])

        print(f"\nDecision change {result.upper()}.")

    elif choice == "r":

        result = reject_review(review["id"])

        print(f"\nDecision change {result.upper()}.")

    else:
        print("\nInvalid choice. Review remains pending.")

print("\n" + "=" * 55)
print("APPROVAL PROCESS COMPLETE")
