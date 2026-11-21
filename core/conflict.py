
import json
import requests

from typing import Literal
from pydantic import BaseModel, Field

from core.memory import retrieve_memory


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"


# ==========================================
# DATA MODELS
# ==========================================

class ConflictFinding(BaseModel):
    previous_decision_id: int
    previous_decision: str
    new_decision: str

    status: Literal[
        "conflict",
        "same_decision",
        "unrelated",
        "uncertain"
    ]

    reason: str


class ConflictReport(BaseModel):
    findings: list[ConflictFinding] = Field(default_factory=list)


# ==========================================
# DATABASE FIELD COMPATIBILITY
# ==========================================

def get_decision_text(decision):

    keys = decision.keys()

    if "decision" in keys:
        return decision["decision"]

    if "description" in keys:
        return decision["description"]

    return ""


# ==========================================
# CONFLICT DETECTION
# ==========================================

def detect_conflicts(new_decisions):

    memory = retrieve_memory()
    previous_decisions = memory["decisions"]

    if not new_decisions:
        return ConflictReport()

    if not previous_decisions:
        return ConflictReport()

    # Prepare previously stored decisions.
    old_data = []

    for decision in previous_decisions:

        old_data.append({
            "id": decision["id"],
            "description": get_decision_text(decision),
            "evidence": decision["source_quote"]
        })

    # Prepare newly extracted decisions.
    new_data = [
        {
            "description": decision.description,
            "evidence": decision.source_quote
        }
        for decision in new_decisions
    ]

    # ======================================
    # AI PROMPT
    # ======================================

    prompt = f"""
You are MeetFlow's decision conflict detection engine.

Compare newly extracted meeting decisions against previously
stored decisions.

PREVIOUS DECISIONS:
{json.dumps(old_data, indent=2)}

NEW DECISIONS:
{json.dumps(new_data, indent=2)}

For every relevant comparison, return a finding.

STATUS DEFINITIONS:

conflict:
A new decision changes, contradicts, or replaces an earlier
decision about the same subject.

same_decision:
The new decision confirms or repeats an existing decision
without changing its meaning.

unrelated:
The decisions concern different subjects and do not affect
each other.

uncertain:
There may be a relationship, but the available evidence
is insufficient to determine whether there is a conflict.

IMPORTANT RULES:

1. Compare the actual meaning, not just matching words.
2. Pay attention to dates, deadlines, amounts and named people.
3. December 5 versus December 10 for the same website launch
   is a conflict.
4. Do not label an unrelated decision as a conflict.
5. Never modify or delete previous decisions.
6. Include a short explanation for every finding.
7. Use the exact previous decision ID supplied above.
8. Do not invent decision IDs.
9. Return valid JSON matching the supplied schema.

Return findings for relevant comparisons.
"""

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": ConflictReport.model_json_schema(),
        "options": {
            "temperature": 0
        }
    }

    # ======================================
    # OLLAMA REQUEST
    # ======================================

    try:

        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=180
        )

        response.raise_for_status()

        generated_text = response.json()["response"]

        parsed_data = json.loads(generated_text)

        return ConflictReport.model_validate(parsed_data)

    except requests.exceptions.ConnectionError:

        raise RuntimeError(
            "Cannot connect to Ollama. Make sure Ollama is running."
        )

    except requests.exceptions.Timeout:

        raise RuntimeError(
            "Conflict detection took too long. Try again."
        )

    except requests.exceptions.RequestException as error:

        raise RuntimeError(
            f"Ollama request failed: {error}"
        )

    except (json.JSONDecodeError, ValueError) as error:

        raise RuntimeError(
            f"Could not validate the conflict report: {error}"
        )
