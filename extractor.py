
import json
import re
import requests

from datetime import date

from typing import Optional
from pydantic import BaseModel, Field

from core.dates import normalize_deadline, parse_deadline


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"


# -----------------------------
# DATA MODELS
# -----------------------------

class Decision(BaseModel):
    description: str
    speaker: Optional[str] = None
    source_quote: str


class ActionItem(BaseModel):
    task: str
    owner: Optional[str] = None
    deadline: Optional[str] = None
    source_quote: str


class MeetingExtraction(BaseModel):
    meeting_title: Optional[str] = None
    meeting_date: Optional[str] = None
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)


# -----------------------------
# SPEAKER RECOVERY
# -----------------------------

def find_quote_speaker(transcript: str, quote: str):
    """
    Find the speaker associated with an evidence quote.
    Returns None if the speaker cannot be established.
    """

    if not quote:
        return None

    for line in transcript.splitlines():
        if ":" not in line:
            continue

        speaker, statement = line.split(":", 1)

        if quote.strip().lower() in statement.strip().lower():
            return speaker.strip()

    return None


# -----------------------------
# DEDUPLICATION
# -----------------------------

def remove_duplicate_decisions(decisions):
    unique = []
    seen = set()

    for decision in decisions:
        key = re.sub(
            r"\s+",
            " ",
            decision.description.strip().lower()
        )

        if key not in seen:
            seen.add(key)
            unique.append(decision)

    return unique


def remove_duplicate_actions(actions):
    unique = []
    seen = set()

    for action in actions:
        key = (
            action.task.strip().lower(),
            (action.owner or "").strip().lower(),
            (action.deadline or "").strip().lower()
        )

        if key not in seen:
            seen.add(key)
            unique.append(action)

    return unique


# -----------------------------
# MAIN EXTRACTION FUNCTION
# -----------------------------

def extract_meeting(transcript: str) -> MeetingExtraction:

    prompt = f"""
You are MeetFlow, a precise meeting intelligence agent.

Analyze the transcript and extract decisions and action items.

DECISIONS:

A decision is a specific outcome or agreement reached
by meeting participants.

Rules:
1. Extract only confirmed decisions.
2. Do not extract agenda topics or discussion starters.
3. Do not classify individual work commitments as decisions.
4. "I will finish the design" is an action item, NOT a decision.
5. "We need to finalize the schedule" is a discussion topic,
   NOT a decision.
6. If multiple speakers confirm the same decision,
   return only ONE decision.
7. Prefer the clearest confirmation as the source quote.
8. Include the specific agreed outcome.

ACTION ITEMS:

1. Extract every task someone commits to performing.
2. Use the speaker label to identify the owner.
3. "I will" and "I'll" mean the speaker owns the task.
4. If someone explicitly assigns a task to another person,
   use that assigned person as owner.
5. Never leave the owner null when the speaker is identifiable
   and the task is their own commitment.
6. Extract deadlines only when explicitly stated. Copy the
   deadline exactly as spoken (for example "November 24" or
   "Friday"). Do not convert it and do not guess a year.
7. Use null for genuinely unknown owners or deadlines.
8. Include an exact supporting quote.

GENERAL RULES:

- Never invent information.
- Preserve the original meaning.
- Do not duplicate decisions or action items.
- Extract meeting title and date if available.
- Return valid JSON matching the supplied schema.

TRANSCRIPT:

{transcript}
"""

    schema = MeetingExtraction.model_json_schema()

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": schema,
        "options": {
            "temperature": 0
        }
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=180
        )

        response.raise_for_status()

        generated_text = response.json()["response"]

        parsed_data = json.loads(generated_text)

        extraction = MeetingExtraction.model_validate(parsed_data)

        # Recover missing action owners from transcript evidence.
        for action in extraction.action_items:
            if not action.owner:
                action.owner = find_quote_speaker(
                    transcript,
                    action.source_quote
                )

        # Turn spoken deadlines into YYYY-MM-DD, resolving words like
        # "Friday" against the meeting date (or today if unknown).
        reference_date = parse_deadline(
            extraction.meeting_date
        ) or date.today()

        for action in extraction.action_items:
            action.deadline = normalize_deadline(
                action.deadline,
                reference_date
            )

        # Remove duplicate entries.
        extraction.decisions = remove_duplicate_decisions(
            extraction.decisions
        )

        extraction.action_items = remove_duplicate_actions(
            extraction.action_items
        )

        return extraction

    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot connect to Ollama. Make sure Ollama is running."
        )

    except requests.exceptions.Timeout:
        raise RuntimeError(
            "The AI model took too long to respond. Try again."
        )

    except requests.exceptions.RequestException as error:
        raise RuntimeError(
            f"Ollama request failed: {error}"
        )

    except (json.JSONDecodeError, ValueError) as error:
        raise RuntimeError(
            f"Could not validate the AI response: {error}"
        )
