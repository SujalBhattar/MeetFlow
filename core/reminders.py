
from datetime import date, datetime, timedelta

from database.db import (
    get_all_actions,
    create_reminder,
    get_owner_email,
)


def parse_deadline(deadline):
    if not deadline:
        return None

    deadline = str(deadline).strip()

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(deadline, fmt).date()
        except ValueError:
            continue

    return None


def check_deadline_reminders():

    today = date.today()
    actions = get_all_actions()

    results = {
        "overdue": [],
        "due_today": [],
        "upcoming": [],
        "skipped": [],
        "email_sent": [],
        "email_skipped": [],
        "email_failed": [],
    }

    for action in actions:

        action_id = action["id"]
        task = action["task"]
        owner = action["owner"] or "Unassigned"

        deadline = parse_deadline(action["deadline"])

        if not deadline:
            results["skipped"].append(task)
            continue

        if action["status"] in ("completed", "cancelled"):
            continue

        if deadline < today:

            reminder_type = "overdue"
            subject = f"MeetFlow: Overdue task - {task}"
            message = (
                f"Your task is overdue.\n\n"
                f"Task: {task}\n"
                f"Owner: {owner}\n"
                f"Deadline: {deadline}\n\n"
                f"Please review its status in MeetFlow."
            )

        elif deadline == today:

            reminder_type = "due_today"
            subject = f"MeetFlow: Task due today - {task}"
            message = (
                f"You have a task due today.\n\n"
                f"Task: {task}\n"
                f"Owner: {owner}\n"
                f"Deadline: {deadline}\n\n"
                f"Please review its status in MeetFlow."
            )

        elif deadline <= today + timedelta(days=2):

            reminder_type = "upcoming"
            subject = f"MeetFlow: Upcoming deadline - {task}"
            message = (
                f"You have an upcoming task deadline.\n\n"
                f"Task: {task}\n"
                f"Owner: {owner}\n"
                f"Deadline: {deadline}\n\n"
                f"Please plan accordingly."
            )

        else:
            continue

        created = create_reminder(
            action_id=action_id,
            reminder_type=reminder_type,
            message=message,
        )

        if not created:
            continue

        results[reminder_type].append(message)

        # ======================================
        # EMAIL DELIVERY
        # ======================================

        if owner == "Unassigned":

            results["email_skipped"].append({
                "task": task,
                "reason": "Task has no assigned owner."
            })

            continue

        recipient = get_owner_email(owner)

        if not recipient:

            results["email_skipped"].append({
                "task": task,
                "owner": owner,
                "reason": "No email address registered."
            })

            continue

        try:

            from integrations.email import send_reminder_email

            send_reminder_email(
                recipient=recipient,
                subject=subject,
                message=message,
            )

            results["email_sent"].append({
                "task": task,
                "owner": owner,
                "email": recipient,
            })

        except Exception as error:

            results["email_failed"].append({
                "task": task,
                "owner": owner,
                "error": str(error),
            })

    return results
