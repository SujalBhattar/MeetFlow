
from pathlib import Path

from core.extractor import extract_meeting


transcript_path = Path("sample_data/meeting_01.txt")

transcript = transcript_path.read_text(encoding="utf-8")

print("\nMeetFlow is analyzing the meeting...\n")

result = extract_meeting(transcript)

print("=" * 55)
print("MEETFLOW MEETING ANALYSIS")
print("=" * 55)

print("\nDECISIONS")

for decision in result.decisions:
    print(f"\n- {decision.description}")
    print(f"  Speaker: {decision.speaker}")
    print(f"  Evidence: {decision.source_quote}")

print("\nACTION ITEMS")

for item in result.action_items:
    print(f"\n- Task: {item.task}")
    print(f"  Owner: {item.owner}")
    print(f"  Deadline: {item.deadline}")
    print(f"  Evidence: {item.source_quote}")

print("\n" + "=" * 55)
print("EXTRACTION COMPLETE")
