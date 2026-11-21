
from collections import defaultdict
from datetime import date, datetime, timedelta

from core.dates import parse_deadline
from database.db import get_all_actions, get_active_decisions


# ==========================================
# WEEKLY DIGEST GENERATOR
# ==========================================

def generate_weekly_digests():

    today = date.today()
    week_end = today + timedelta(days=7)

    actions = get_all_actions()
    decisions = get_active_decisions()

    people = defaultdict(lambda: {
        "tasks": [],
        "completed": [],
        "pending": [],
        "in_progress": [],
        "cancelled": [],
        "overdue": [],
        "upcoming": [],
        "decisions": [],
        "completion_rate": 0,
    })

    # ======================================
    # GROUP ACTION ITEMS BY OWNER
    # ======================================

    for action in actions:

        owner = action["owner"] or "Unassigned"

        person = people[owner]

        deadline = parse_deadline(action["deadline"])

        status = (
            action["status"] or "pending"
        ).strip().lower()

        if status not in (
            "pending",
            "in_progress",
            "completed",
            "cancelled",
            "exported"
        ):
            status = "pending"

        task_data = {
            "id": action["id"],
            "task": action["task"],
            "deadline": action["deadline"] or "Not specified",
            "status": status,
            "meeting": action["meeting_title"] or "Unknown",
        }

        # Keep every task in the complete task list.
        person["tasks"].append(task_data)

        # Categorize task status.
        if status == "completed":

            person["completed"].append(task_data)

        elif status == "cancelled":

            person["cancelled"].append(task_data)

        elif status == "in_progress":

            person["in_progress"].append(task_data)

        else:

            # Both pending and exported tasks remain unfinished.
            person["pending"].append(task_data)

        # Categorize deadlines only for unfinished tasks.
        if status not in ("completed", "cancelled"):

            if deadline and deadline < today:

                person["overdue"].append(task_data)

            elif deadline and today <= deadline <= week_end:

                person["upcoming"].append(task_data)

    # ======================================
    # GROUP DECISIONS BY SPEAKER
    # ======================================

    for decision in decisions:

        speaker = decision["speaker"] or "Unassigned"

        # Support both database column names.
        keys = decision.keys()

        description = (
            decision["decision"]
            if "decision" in keys
            else decision["description"]
        )

        people[speaker]["decisions"].append({
            "decision": description,
            "meeting": decision["meeting_title"] or "Unknown",
        })

    # ======================================
    # CALCULATE COMPLETION PERCENTAGE
    # ======================================

    for person_data in people.values():

        total_active = (
            len(person_data["tasks"])
            - len(person_data["cancelled"])
        )

        completed = len(person_data["completed"])

        person_data["completion_rate"] = (
            round((completed / total_active) * 100)
            if total_active else 0
        )

    # ======================================
    # RETURN WEEKLY DIGEST
    # ======================================

    return {
        "generated_on": today.isoformat(),
        "period_end": week_end.isoformat(),
        "people": dict(people),
    }
