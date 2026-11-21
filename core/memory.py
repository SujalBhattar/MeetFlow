
from database.db import (
    initialize_database,
    save_decision,
    save_action,
    get_all_decisions,
    get_all_actions
)


def remember_meeting(extraction):

    initialize_database()

    for decision in extraction.decisions:
        save_decision(
            extraction.meeting_title,
            decision
        )

    for action in extraction.action_items:
        save_action(
            extraction.meeting_title,
            action
        )


def retrieve_memory():

    initialize_database()

    return {
        "decisions": get_all_decisions(),
        "actions": get_all_actions()
    }
