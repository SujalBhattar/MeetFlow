from datetime import date, timedelta

from core.dates import parse_deadline
from database.db import (
    create_reminder,
    get_all_actions,
    get_owner_email,
    get_reminder,
    mark_reminder_emailed,
)


def _default_sender(recipient, subject, message):
    # Imported lazily so the app still works without email configured.
    from integrations.email import send_reminder_email

    return send_reminder_email(
        recipient=recipient,
        subject=subject,
        message=message,
    )


def check_deadline_reminders(today=None, send_email=_default_sender):
    """Create reminders for overdue, due-today and upcoming tasks.

    Each (task, reminder type) pair is created once. Emails are tracked
    separately: if sending fails, or the owner's address is added later,
    the next check tries again until the email has gone out.
    """

    today = today or date.today()

    results = {
        "overdue": [],
        "due_today": [],
        "upcoming": [],
        "skipped": [],
        "email_sent": [],
        "email_skipped": [],
        "email_failed": [],
    }

    for action in get_all_actions():

        if action["status"] in ("completed", "cancelled"):
            continue

        task = action["task"]
        owner = action["owner"] or "Unassigned"
        deadline = parse_deadline(action["deadline"], today)

        if not deadline:
            results["skipped"].append(task)
            continue

        if deadline < today:
            reminder_type = "overdue"
            subject = f"MeetFlow: Overdue task - {task}"
            intro = "Your task is overdue."
            outro = "Please review its status in MeetFlow."

        elif deadline == today:
            reminder_type = "due_today"
            subject = f"MeetFlow: Task due today - {task}"
            intro = "You have a task due today."
            outro = "Please review its status in MeetFlow."

        elif deadline <= today + timedelta(days=2):
            reminder_type = "upcoming"
            subject = f"MeetFlow: Upcoming deadline - {task}"
            intro = "You have an upcoming task deadline."
            outro = "Please plan accordingly."

        else:
            continue

        message = (
            f"{intro}\n\n"
            f"Task: {task}\n"
            f"Owner: {owner}\n"
            f"Deadline: {deadline}\n\n"
            f"{outro}"
        )

        created = create_reminder(
            action_id=action["id"],
            reminder_type=reminder_type,
            message=message,
        )

        if created:
            results[reminder_type].append(message)

        reminder = get_reminder(action["id"], reminder_type)

        if reminder["emailed_at"]:
            continue

        if owner == "Unassigned":
            if created:
                results["email_skipped"].append({
                    "task": task,
                    "reason": "Task has no assigned owner.",
                })
            continue

        recipient = get_owner_email(owner)

        if not recipient:
            if created:
                results["email_skipped"].append({
                    "task": task,
                    "owner": owner,
                    "reason": "No email address registered.",
                })
            continue

        try:
            send_email(
                recipient=recipient,
                subject=subject,
                message=message,
            )

            mark_reminder_emailed(reminder["id"])

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
