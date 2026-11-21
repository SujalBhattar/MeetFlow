
from pathlib import Path

from core.extractor import extract_meeting
from core.memory import remember_meeting, retrieve_memory


transcript = Path(
    "sample_data/meeting_01.txt"
).read_text(encoding="utf-8")

print("Analyzing meeting...")

result = extract_meeting(transcript)

remember_meeting(result)

memory = retrieve_memory()

print("\nMEETFLOW STORED MEMORY")
print("=" * 45)

print("\nDECISIONS:")

for decision in memory["decisions"]:
    print("-", decision["decision"])

print("\nACTION ITEMS:")

for action in memory["actions"]:
    print(
        f"- {action['task']} | "
        f"Owner: {action['owner']} | "
        f"Deadline: {action['deadline']}"
    )
