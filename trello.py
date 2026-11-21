
import os
import requests
from dotenv import load_dotenv

from core.dates import parse_deadline

load_dotenv()

BASE_URL = "https://api.trello.com/1"

API_KEY = os.getenv("TRELLO_API_KEY")
TOKEN = os.getenv("TRELLO_TOKEN")
BOARD_ID = os.getenv("TRELLO_BOARD_ID")
TODO_LIST_ID = os.getenv("TRELLO_TODO_LIST_ID")


def get_auth_params():
    if not API_KEY or not TOKEN:
        raise RuntimeError(
            "Trello API key or token missing from .env"
        )

    return {
        "key": API_KEY,
        "token": TOKEN
    }


def test_connection():
    response = requests.get(
        f"{BASE_URL}/members/me",
        params=get_auth_params(),
        timeout=20
    )
    response.raise_for_status()
    return response.json()


def verify_board():
    if not BOARD_ID:
        raise RuntimeError("Trello board ID missing from .env")

    response = requests.get(
        f"{BASE_URL}/boards/{BOARD_ID}",
        params=get_auth_params(),
        timeout=20
    )
    response.raise_for_status()
    return response.json()


def verify_todo_list():
    if not TODO_LIST_ID:
        raise RuntimeError("Trello To Do list ID missing from .env")

    response = requests.get(
        f"{BASE_URL}/lists/{TODO_LIST_ID}",
        params=get_auth_params(),
        timeout=20
    )
    response.raise_for_status()
    return response.json()


def create_card(name, description="", due=None):
    if not name or not name.strip():
        raise ValueError("Card name cannot be empty.")

    if not TODO_LIST_ID:
        raise RuntimeError("Trello To Do list ID missing from .env")

    payload = {
        **get_auth_params(),
        "idList": TODO_LIST_ID,
        "name": name.strip(),
        "desc": description
    }

    if due:
        payload["due"] = due

    response = requests.post(
        f"{BASE_URL}/cards",
        params=payload,
        timeout=20
    )
    response.raise_for_status()
    return response.json()


def create_action_card(action):
    """Create a Trello card from an action-item database row."""

    description = f"""
MEETING: {action['meeting_title'] or 'Unknown'}

OWNER: {action['owner'] or 'Unassigned'}

DEADLINE: {action['deadline'] or 'Not specified'}

SOURCE EVIDENCE:
{action['source_quote'] or 'No source quote available'}

CREATED BY: MeetFlow
"""

    deadline = parse_deadline(action["deadline"])

    return create_card(
        name=action["task"],
        description=description.strip(),
        due=f"{deadline.isoformat()}T12:00:00.000Z" if deadline else None
    )
