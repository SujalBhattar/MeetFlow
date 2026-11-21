
import sqlite3
from pathlib import Path


# Preserve the existing database location.
DB_PATH = Path(r"data/meetflow\.db")


VALID_ACTION_STATUSES = (
    "pending",
    "in_progress",
    "completed",
    "cancelled",
    "exported",
)


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_connection():

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    return connection


# ==========================================
# DATABASE INITIALIZATION
# ==========================================

def initialize_database():

    with get_connection() as connection:

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

        # Owner email directory.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS owner_emails (
                owner TEXT PRIMARY KEY COLLATE NOCASE,
                email TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Safe migrations for existing databases.
        action_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(action_items)"
            ).fetchall()
        }

        if "trello_card_id" not in action_columns:

            connection.execute(
                "ALTER TABLE action_items ADD COLUMN trello_card_id TEXT"
            )

        if "trello_card_url" not in action_columns:

            connection.execute(
                "ALTER TABLE action_items ADD COLUMN trello_card_url TEXT"
            )


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


def get_all_decisions():

    with get_connection() as connection:

        return connection.execute("""
            SELECT * FROM decisions
            ORDER BY created_at DESC
        """).fetchall()


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
            ORDER BY created_at DESC
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
# DECISION APPROVALS
# ==========================================

def create_review(
    old_decision_id,
    new_decision,
    meeting_title,
    reason
):

    with get_connection() as connection:

        cursor = connection.execute("""
            INSERT INTO decision_reviews
            (old_decision_id, new_decision, meeting_title, reason)
            VALUES (?, ?, ?, ?)
        """, (
            old_decision_id,
            new_decision,
            meeting_title,
            reason
        ))

        return cursor.lastrowid


def get_pending_reviews():

    with get_connection() as connection:

        return connection.execute("""
            SELECT * FROM decision_reviews
            WHERE status = 'pending'
            ORDER BY created_at DESC
        """).fetchall()


def resolve_review(review_id, status):

    if status not in ("approved", "rejected"):
        raise ValueError("Invalid review status.")

    with get_connection() as connection:

        connection.execute("""
            UPDATE decision_reviews
            SET status = ?
            WHERE id = ?
        """, (status, review_id))


# ==========================================
# REMINDERS
# ==========================================

def create_reminder(action_id, reminder_type, message):

    with get_connection() as connection:

        cursor = connection.execute("""
            INSERT OR IGNORE INTO reminders
            (action_id, reminder_type, message)
            VALUES (?, ?, ?)
        """, (
            action_id,
            reminder_type,
            message
        ))

        return cursor.rowcount > 0


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
            ORDER BY reminders.created_at DESC
        """).fetchall()


def get_action_reminders(action_id):

    with get_connection() as connection:

        return connection.execute("""
            SELECT * FROM reminders
            WHERE action_id = ?
            ORDER BY created_at DESC
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

    owner = str(owner).strip()

    with get_connection() as connection:

        result = connection.execute("""
            SELECT email
            FROM owner_emails
            WHERE owner = ?
        """, (owner,)).fetchone()

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


# ==========================================
# INITIALIZE DATABASE
# ==========================================

initialize_database()
