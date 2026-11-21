from database.db import (
    initialize_database,
    save_decision,
    save_action,
    get_active_decisions,
    get_all_actions
)


def remember_meeting(extraction):
    """Store every decision and action item from an extraction."""

    initialize_database()

    for decision in extraction.decisions:
        save_decision(
            extraction.meeting_title,
            decision.description,
            decision.speaker,
            decision.source_quote
        )

    for action in extraction.action_items:
        save_action(
            extraction.meeting_title,
            action.task,
            action.owner,
            action.deadline,
            action.source_quote
        )


def retrieve_memory():
    """Active decisions (superseded ones are history) and all actions."""

    initialize_database()

    return {
        "decisions": get_active_decisions(),
        "actions": get_all_actions()
    }
