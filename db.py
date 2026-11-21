"""SQLite storage layer for MeetFlow.

Every other module talks to the database through the functions here.
The schema is created (and upgraded) automatically the first time a
connection is opened, so there is no import-time side effect.
"""

import hashlib
import shutil
import sqlite3
from contextlib import contextmanager
from pathlib import Path


# The database lives at data/meetflow.db.
# (Older versions used the string r"data/meetflow\.db". On Windows that
# created a folder called "meetflow" holding a file called ".db".
# _migrate_legacy_database() moves that data to the right place.)
DEFAULT_DB_PATH = Path("data") / "meetflow.db"
DB_PATH = DEFAULT_DB_PATH


VALID_ACTION_STATUSES = (
    "pending",
    "in_progress",
    "completed",
    "cancelled",
    "exported",
)

# Database files whose schema has already been checked in this process.
_READY = set()


# ==========================================
# DATABASE CONNECTION
# ==========================================

@contextmanager
def get_connection():
    """Open a connection that commits on success and always closes."""

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if str(DB_PATH) not in _READY:
        _migrate_legacy_database()

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        if str(DB_PATH) not in _READY:
            _create_schema(connection)
            _READY.add(str(DB_PATH))

        yield connection
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def _migrate_legacy_database():
    """Move data from the old data/meetflow/.db file, if it exists.

    Nothing is deleted: any database already at the new location is
    backed up first, and the legacy file is renamed, not removed.
    """

    legacy = DB_PATH.parent / DB_PATH.stem / ".db"

    if not legacy.is_file():
        return

    if DB_PATH.exists():
        backup = DB_PATH.with_name(f"{DB_PATH.stem}.before-migration.db")
        shutil.copy2(DB_PATH, backup)

    shutil.copy2(legacy, DB_PATH)
    legacy.rename(legacy.with_name(".db.migrated"))


# ==========================================
# SCHEMA
# ==========================================

def _add_column_if_missing(connection, table, column, definition):

    existing = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})")
    }

    if column not in existing:
        connection.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def _create_schema(connection):

    connection.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_title TEXT,
            decision TEXT NOT NULL,
            speaker TEXT,
            source_quote TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS action_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_title TEXT,
            task TEXT NOT NULL,
            owner TEXT,
            deadline TEXT,
            source_quote TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS decision_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            old_decision_id INTEGER,
            new_decision TEXT,
            meeting_title TEXT,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_id INTEGER NOT NULL,
            reminder_type TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(action_id, reminder_type),
            FOREIGN KEY(action_id) REFERENCES action_items(id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS owner_emails (
            owner TEXT PRIMARY KEY COLLATE NOCASE,
            email TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            transcript_hash TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Safe migrations for databases created by older versions.
    _add_column_if_missing(
        connection, "action_items", "trello_card_id", "TEXT"
    )
    _add_column_if_missing(
        connection, "action_items", "trello_card_url", "TEXT"
    )
    _add_column_if_missing(
        connection, "decision_reviews", "previous_decision", "TEXT"
    )
    _add_column_if_missing(
        connection, "decision_reviews", "speaker", "TEXT"
    )
    _add_column_if_missing(
        connection, "decision_reviews", "source_quote", "TEXT"
    )
    _add_column_if_missing(
        connection, "reminders", "emailed_at", "TIMESTAMP"
    )


def initialize_database():
    """Make sure the database file and all tables exist."""

    with get_connection():
        pass


# ==========================================
# DECISIONS
# ==========================================

def save_decision(
    meeting_title,
    decision,
    speaker=None,
    source_quote=None
):

    with get_connection() as connection:

        cursor = connection.execute("""
            INSERT INTO decisions
            (meeting_title, decision, speaker, source_quote)
            VALUES (?, ?, ?, ?)
        """, (
            meeting_title,
            decision,
            speaker,
            source_quote
        ))

        return cursor.lastrowid


def get_all_decisions(status=None):
    """All decisions, newest first. Pass status="active" to filter."""

    query = "SELECT * FROM decisions"
    params = ()

    if status:
        query += " WHERE status = ?"
        params = (status,)

    query += " ORDER BY created_at DESC, id DESC"

    with get_connection() as connection:
        return connection.execute(query, params).fetchall()


def get_active_decisions():
    return get_all_decisions(status="active")


# ==========================================
# ACTION ITEMS
# ==========================================

def save_action(
    meeting_title,
    task,
    owner=None,
    deadline=None,
    source_quote=None
):

    with get_connection() as connection:

        cursor = connection.execute("""
            INSERT INTO action_items
            (meeting_title, task, owner, deadline, source_quote)
            VALUES (?, ?, ?, ?, ?)
        """, (
            meeting_title,
            task,
            owner,
            deadline,
            source_quote
        ))

        return cursor.lastrowid


def get_all_actions():

    with get_connection() as connection:

        return connection.execute("""
            SELECT * FROM action_items
            ORDER BY created_at DESC, id DESC
        """).fetchall()


def update_action_status(action_id, status):

    status = str(status).strip().lower()

    if status not in VALID_ACTION_STATUSES:
        raise ValueError("Invalid action status.")

    with get_connection() as connection:

        cursor = connection.execute("""
            UPDATE action_items
            SET status = ?
            WHERE id = ?
        """, (status, action_id))

        if cursor.rowcount == 0:
            raise ValueError("Action not found.")


def mark_action_exported(action_id, card_id, card_url):

    with get_connection() as connection:

        cursor = connection.execute("""
            UPDATE action_items
            SET trello_card_id = ?,
                trello_card_url = ?,
                status = 'exported'
            WHERE id = ?
              AND trello_card_id IS NULL
        """, (card_id, card_url, action_id))

        if cursor.rowcount == 0:
            raise ValueError(
                "Action was already exported or could not be found."
            )


# ==========================================
# MEETINGS
# ==========================================

def transcript_hash(transcript):
    return hashlib.sha256(transcript.encode("utf-8")).hexdigest()


def meeting_exists(transcript):
    """True if this exact transcript was already analyzed."""

    with get_connection() as connection:

        row = connection.execute(
            "SELECT 1 FROM meetings WHERE transcript_hash = ?",
            (transcript_hash(transcript),)
        ).fetchone()

        return row is not None


def record_meeting(title, transcript):

    with get_connection() as connection:

        connection.execute("""
            INSERT OR IGNORE INTO meetings (title, transcript_hash)
            VALUES (?, ?)
        """, (title, transcript_hash(transcript)))


def get_meeting_history():

    with get_connection() as connection:

        return connection.execute("""
            SELECT * FROM meetings
            ORDER BY id DESC
        """).fetchall()


# ==========================================
# DECISION APPROVALS
# ==========================================

def create_review(
    previous_id,
    previous_decision,
    new_decision,
    reason,
    meeting_title=None,
    speaker=None,
    source_quote=None
):
    """Queue a decision change for human approval.

    If the same change is already waiting, its id is returned instead
    of creating a duplicate.
    """

    with get_connection() as connection:

        existing = connection.execute("""
            SELECT id FROM decision_reviews
            WHERE status = 'pending'
              AND old_decision_id IS ?
              AND new_decision = ?
        """, (previous_id, new_decision)).fetchone()

        if existing:
            return existing["id"]

        cursor = connection.execute("""
            INSERT INTO decision_reviews
            (old_decision_id, previous_decision, new_decision,
             meeting_title, reason, speaker, source_quote)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            previous_id,
            previous_decision,
            new_decision,
            meeting_title,
            reason,
            speaker,
            source_quote
        ))

        return cursor.lastrowid


def get_pending_reviews():

    with get_connection() as connection:

        return connection.execute("""
            SELECT * FROM decision_reviews
            WHERE status = 'pending'
            ORDER BY created_at DESC, id DESC
        """).fetchall()


def resolve_review(review_id, status):
    """Approve or reject a pending review.

    Approving replaces the old decision: it is marked "superseded" and
    the new decision becomes active. Rejecting changes nothing else.
    Everything happens in a single transaction.
    """

    if status not in ("approved", "rejected"):
        raise ValueError("Invalid review status.")

    with get_connection() as connection:

        review = connection.execute(
            "SELECT * FROM decision_reviews WHERE id = ?",
            (review_id,)
        ).fetchone()

        if review is None:
            raise ValueError("Review not found.")

        if review["status"] != "pending":
            raise ValueError("This review was already resolved.")

        connection.execute(
            "UPDATE decision_reviews SET status = ? WHERE id = ?",
            (status, review_id)
        )

        if status != "approved":
            return

        if review["old_decision_id"] is not None:
            connection.execute("""
                UPDATE decisions
                SET status = 'superseded'
                WHERE id = ? AND status = 'active'
            """, (review["old_decision_id"],))

        already_active = connection.execute("""
            SELECT 1 FROM decisions
            WHERE status = 'active' AND decision = ?
        """, (review["new_decision"],)).fetchone()

        if not already_active:
            connection.execute("""
                INSERT INTO decisions
                (meeting_title, decision, speaker, source_quote)
                VALUES (?, ?, ?, ?)
            """, (
                review["meeting_title"],
                review["new_decision"],
                review["speaker"],
                review["source_quote"]
            ))


# ==========================================
# REMINDERS
# ==========================================

def create_reminder(action_id, reminder_type, message):
    """Create a reminder. Returns True only if it is new."""

    with get_connection() as connection:

        cursor = connection.execute("""
            INSERT OR IGNORE INTO reminders
            (action_id, reminder_type, message)
            VALUES (?, ?, ?)
        """, (action_id, reminder_type, message))

        return cursor.rowcount > 0


def get_reminder(action_id, reminder_type):

    with get_connection() as connection:

        return connection.execute("""
            SELECT * FROM reminders
            WHERE action_id = ? AND reminder_type = ?
        """, (action_id, reminder_type)).fetchone()


def mark_reminder_emailed(reminder_id):

    with get_connection() as connection:

        connection.execute("""
            UPDATE reminders
            SET emailed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (reminder_id,))


def get_all_reminders():

    with get_connection() as connection:

        return connection.execute("""
            SELECT reminders.*,
                   action_items.task,
                   action_items.owner,
                   action_items.deadline
            FROM reminders
            JOIN action_items
                ON reminders.action_id = action_items.id
            ORDER BY reminders.created_at DESC, reminders.id DESC
        """).fetchall()


def get_action_reminders(action_id):

    with get_connection() as connection:

        return connection.execute("""
            SELECT * FROM reminders
            WHERE action_id = ?
            ORDER BY created_at DESC, id DESC
        """, (action_id,)).fetchall()


# ==========================================
# OWNER EMAIL DIRECTORY
# ==========================================

def save_owner_email(owner, email):

    owner = str(owner).strip()
    email = str(email).strip()

    if not owner:
        raise ValueError("Owner name cannot be empty.")

    if not email or "@" not in email:
        raise ValueError("Please provide a valid email address.")

    with get_connection() as connection:

        connection.execute("""
            INSERT INTO owner_emails (owner, email)
            VALUES (?, ?)
            ON CONFLICT(owner)
            DO UPDATE SET
                email = excluded.email,
                updated_at = CURRENT_TIMESTAMP
        """, (owner, email))


def get_owner_email(owner):

    if not owner:
        return None

    with get_connection() as connection:

        result = connection.execute("""
            SELECT email
            FROM owner_emails
            WHERE owner = ?
        """, (str(owner).strip(),)).fetchone()

        return result["email"] if result else None


def get_all_owner_emails():

    with get_connection() as connection:

        return connection.execute("""
            SELECT owner, email, updated_at
            FROM owner_emails
            ORDER BY owner COLLATE NOCASE
        """).fetchall()


def delete_owner_email(owner):

    if not owner:
        raise ValueError("Owner name cannot be empty.")

    with get_connection() as connection:

        cursor = connection.execute("""
            DELETE FROM owner_emails
            WHERE owner = ?
        """, (str(owner).strip(),))

        return cursor.rowcount > 0
