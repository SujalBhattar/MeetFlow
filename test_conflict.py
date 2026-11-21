
from pathlib import Path

from core.extractor import extract_meeting
from core.conflict import detect_conflicts


transcript_path = Path("sample_data/meeting_02.txt")
transcript = transcript_path.read_text(encoding="utf-8")

print("\nMeetFlow is analyzing the new meeting...\n")

extraction = extract_meeting(transcript)

print("=" * 55)
print("NEW MEETING DECISIONS")
print("=" * 55)

for decision in extraction.decisions:
    print(f"\n- {decision.description}")
    print(f"  Evidence: {decision.source_quote}")

print("\nChecking previous meeting memory...")

report = detect_conflicts(extraction.decisions)

print("\n" + "=" * 55)
print("MEETFLOW CONFLICT DETECTION")
print("=" * 55)

if not report.findings:
    print("\nNo relevant previous decisions found.")

for finding in report.findings:
    print(f"\nStatus: {finding.status.upper()}")
    print(f"Previous: {finding.previous_decision}")
    print(f"New: {finding.new_decision}")
    print(f"Reason: {finding.reason}")

print("\n" + "=" * 55)
print("CONFLICT ANALYSIS COMPLETE")
