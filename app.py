
from datetime import datetime

import streamlit as st
import pandas as pd

from core.reminders import check_deadline_reminders
from core.digest import generate_weekly_digests
from core.extractor import extract_meeting
from core.conflict import detect_conflicts
from core.approval import (
    create_pending_reviews,
    get_reviews,
    approve_review,
    reject_review
)

from database.db import (
    initialize_database,
    get_connection,
    get_all_decisions,
    get_active_decisions,
    get_all_actions,
    get_all_reminders,
    get_meeting_history,
    meeting_exists,
    record_meeting,
    save_decision,
    save_action,
    mark_action_exported,
    update_action_status,
    save_owner_email,
    get_owner_email,
    get_all_owner_emails,
    delete_owner_email
)

from integrations.trello import (
    test_connection,
    verify_board,
    create_action_card
)


# ==========================================
# PAGE CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="MeetFlow | Meeting Intelligence",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ==========================================
# DATABASE HELPERS
# ==========================================

def get_decision_history():
    with get_connection() as connection:
        return connection.execute("""
            SELECT * FROM decisions
            ORDER BY id DESC
        """).fetchall()


def save_extraction(extraction, report):

    conflict_descriptions = {
        finding.new_decision
        for finding in report.findings
        if finding.status == "conflict"
    }

    repeated_descriptions = {
        finding.new_decision
        for finding in report.findings
        if finding.status == "same_decision"
    }

    existing_decisions = get_all_decisions()
    saved_decision_keys = set()

    for row in existing_decisions:

        keys = row.keys()

        description = (
            row["decision"]
            if "decision" in keys
            else row["description"]
        )

        saved_decision_keys.add((
            description,
            row["source_quote"]
        ))

    for decision in extraction.decisions:

        if decision.description in conflict_descriptions:
            continue

        if decision.description in repeated_descriptions:
            continue

        decision_key = (
            decision.description,
            decision.source_quote
        )

        if decision_key not in saved_decision_keys:

            save_decision(
                extraction.meeting_title,
                decision.description,
                decision.speaker,
                decision.source_quote
            )

            saved_decision_keys.add(decision_key)

    existing_actions = get_all_actions()

    saved_action_keys = {
        (
            row["task"],
            row["owner"],
            row["deadline"],
            row["source_quote"]
        )
        for row in existing_actions
    }

    for action in extraction.action_items:

        action_key = (
            action.task,
            action.owner,
            action.deadline,
            action.source_quote
        )

        if action_key not in saved_action_keys:

            save_action(
                extraction.meeting_title,
                action.task,
                action.owner,
                action.deadline,
                action.source_quote
            )

            saved_action_keys.add(action_key)


# ==========================================
# INITIALIZATION
# ==========================================

initialize_database()


# ==========================================
# DESIGN SYSTEM
# ==========================================

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&display=swap');

    :root {
        --canvas: #F4F2E9;
        --surface: #FFFFFF;
        --forest: #345A45;
        --forest-dark: #263D31;
        --sage: #89977C;
        --muted: #81877D;
        --border: #E7E6DC;
        --ink: #29352C;
    }

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }

    .stApp {
        background: var(--canvas);
        color: var(--ink);
    }

    .block-container {
        max-width: 1450px;
        padding: 2.5rem 3rem 4rem 3rem;
    }

    section[data-testid="stSidebar"] {
        background: #EAECE2;
        border-right: 1px solid #DDE1D5;
    }

    section[data-testid="stSidebar"] > div {
        padding: 2rem 1.2rem;
    }

    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #6F796D;
    }

    section[data-testid="stSidebar"] .stRadio label {
        padding: 9px 12px;
        border-radius: 9px;
        font-weight: 500;
        transition: 0.2s ease;
    }

    section[data-testid="stSidebar"] .stRadio label:hover {
        background: #DDE4D7;
        color: var(--forest-dark);
    }

    h1, h2, h3 {
        color: var(--forest-dark) !important;
        font-family: 'Fraunces', serif !important;
        letter-spacing: -0.6px;
    }

    h1 {
        font-size: 2.5rem !important;
        font-weight: 600 !important;
    }

    h2 {
        font-size: 1.8rem !important;
    }

    h3 {
        font-size: 1.35rem !important;
    }

    p, li, label {
        color: var(--ink);
    }

    [data-testid="stMetric"] {
        background: var(--surface);
        padding: 1.35rem;
        border: 1px solid var(--border);
        border-radius: 15px;
        box-shadow: 0 2px 8px rgba(42, 57, 43, 0.025);
    }

    [data-testid="stMetricLabel"] {
        color: var(--muted);
        font-size: 0.85rem;
        font-weight: 600;
    }

    [data-testid="stMetricValue"] {
        color: var(--forest);
        font-size: 2rem;
        font-weight: 700;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 15px;
        padding: 0.7rem;
    }

    .stButton > button,
    .stDownloadButton > button {
        border-radius: 10px;
        border: 1px solid #D9DED4;
        padding: 0.65rem 1.1rem;
        font-weight: 600;
        transition: all 0.2s ease;
        background: white;
        color: var(--forest-dark);
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover {
        border-color: var(--forest);
        color: var(--forest);
        background: #F0F4ED;
    }

    .stButton > button[kind="primary"] {
        background: var(--forest);
        color: white;
        border: 1px solid var(--forest);
    }

    .stButton > button[kind="primary"]:hover {
        background: var(--forest-dark);
        border-color: var(--forest-dark);
        color: white;
    }

    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox div[data-baseweb="select"] > div {
        border-radius: 9px;
        border-color: var(--border);
        background: white;
    }

    .stTextArea textarea:focus,
    .stTextInput input:focus {
        border-color: var(--forest);
        box-shadow: 0 0 0 1px var(--forest);
    }

    [data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 12px;
        overflow: hidden;
    }

    button[data-baseweb="tab"] {
        font-weight: 600;
        color: var(--muted);
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color: var(--forest);
        border-bottom-color: var(--forest);
    }

    hr {
        border-color: var(--border);
    }

    [data-testid="stProgressBar"] > div > div {
        background: var(--forest);
    }

    [data-testid="stAlert"] {
        border-radius: 12px;
        border: 1px solid var(--border);
    }

    [data-testid="stFileUploader"] {
        background: white;
        border: 1px dashed #B8C5B4;
        border-radius: 14px;
        padding: 1rem;
    }

    .brand-title {
        font-family: 'Fraunces', serif;
        font-size: 1.8rem;
        font-weight: 700;
        color: var(--forest-dark);
        letter-spacing: -1px;
    }

    .brand-caption {
        color: #879080;
        font-size: 0.75rem;
        letter-spacing: 1.3px;
        text-transform: uppercase;
    }

    .eyebrow {
        color: var(--sage);
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.8px;
    }

    .hero-title {
        font-family: 'Fraunces', serif;
        font-size: 2.7rem;
        font-weight: 600;
        color: var(--forest-dark);
        letter-spacing: -1.4px;
        line-height: 1.15;
    }

    .hero-caption {
        color: #81877D;
        font-size: 1rem;
        margin-top: 0.5rem;
    }

    .section-caption {
        color: #81877D;
        font-size: 0.9rem;
    }

    .footer-note {
        color: #92998D;
        font-size: 0.75rem;
        text-align: center;
        letter-spacing: 1px;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# SIDEBAR
# ==========================================

with st.sidebar:

    st.markdown(
        '<div class="brand-title">MeetFlow.</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="brand-caption">Meetings into momentum</div>',
        unsafe_allow_html=True
    )

    st.write("")
    st.divider()

    st.markdown("##### WORKSPACE")

    page = st.radio(
        "NAVIGATION",
        [
            "Overview",
            "Analyze Meeting",
            "Decisions",
            "Action Items",
            "Approvals",
            "Trello Export",
            "Deadline Reminders",
            "Weekly Digest",
            "Email Directory"
        ],
        label_visibility="collapsed"
    )

    st.divider()

    st.markdown("##### YOUR SYSTEM")

    st.markdown("**Local AI engine**")
    st.caption("● Ollama · llama3.2:3b")

    st.write("")

    st.markdown("**Task integration**")
    st.caption("● Trello workspace")

    st.divider()

    st.markdown(
        '<div class="footer-note">MEETFLOW · MVP 01</div>',
        unsafe_allow_html=True
    )


# ==========================================
# FETCH DATABASE DATA
# ==========================================

decisions = get_active_decisions()
actions = get_all_actions()
reviews = get_reviews()
meetings = get_meeting_history()


# ==========================================
# OVERVIEW PAGE
# ==========================================

if page == "Overview":

    current_hour = datetime.now().hour

    if current_hour < 12:
        greeting = "Good morning"
    elif current_hour < 18:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    st.markdown(
        '<div class="eyebrow">YOUR WORKSPACE</div>'
        f'<div class="hero-title">{greeting}.</div>'
        '<div class="hero-caption">'
        'A little more clarity. A lot more momentum.'
        '</div>',
        unsafe_allow_html=True
    )

    st.write("")
    st.write("")

    exported_count = sum(
        1 for action in actions
        if action["trello_card_id"]
    )

    completed_count = sum(
        1 for action in actions
        if action["status"] == "completed"
    )

    pending_count = sum(
        1 for action in actions
        if action["status"] in ("pending", "exported")
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Meetings analyzed", len(meetings))
    col2.metric("Active decisions", len(decisions))
    col3.metric("Action items", len(actions))
    col4.metric("Exported to Trello", exported_count)

    st.write("")
    st.divider()

    col1, col2 = st.columns([1.5, 1])

    with col1:

        st.subheader("Recent meetings")
        st.caption("Your latest meeting intelligence.")

        if meetings:

            for meeting in meetings[:5]:

                with st.container(border=True):

                    st.markdown(
                        f"**{meeting['title'] or 'Untitled meeting'}**"
                    )

                    st.caption(
                        f"Meeting ID: {meeting['id']} · "
                        f"{meeting['created_at']}"
                    )

        else:
            st.info(
                "Your workspace is waiting for its first meeting."
            )

    with col2:

        st.subheader("Task progress")
        st.caption("A snapshot of your team's workload.")

        if actions:

            completion_rate = completed_count / len(actions)

            st.metric(
                "Completed tasks",
                f"{completed_count} / {len(actions)}"
            )

            st.progress(completion_rate)

            st.caption(
                f"{round(completion_rate * 100)}% completion"
            )

            st.write("")

            st.metric("Pending tasks", pending_count)
            st.metric("Trello exports", exported_count)

        else:
            st.info("No tasks to track yet.")

    st.divider()

    st.subheader("Active decisions")
    st.caption("Previously agreed decisions stored in memory.")

    if decisions:

        for decision in decisions[:5]:

            with st.container(border=True):

                description = (
                    decision["decision"]
                    if "decision" in decision.keys()
                    else decision["description"]
                )

                st.markdown(f"**{description}**")

                st.caption(
                    f"Meeting: {decision['meeting_title'] or 'Unknown'}"
                )

    else:
        st.info("No active decisions stored yet.")

    if reviews:
        st.warning(
            f"{len(reviews)} decision change(s) are waiting for approval."
        )

    st.write("")
    st.markdown(
        '<div class="footer-note">MEETFLOW · MEETINGS INTO MOMENTUM</div>',
        unsafe_allow_html=True
    )


# ==========================================
# ANALYZE MEETING PAGE
# ==========================================

elif page == "Analyze Meeting":

    st.markdown(
        '<div class="eyebrow">MEETING INTELLIGENCE</div>',
        unsafe_allow_html=True
    )

    st.title("Analyze a meeting")

    st.caption(
        "Turn conversations into decisions, responsibilities and action."
    )

    st.write("")

    uploaded_file = st.file_uploader(
        "Upload meeting transcript",
        type=["txt"]
    )

    if uploaded_file:

        transcript = uploaded_file.read().decode(
            "utf-8",
            errors="replace"
        )

        st.text_area(
            "Transcript preview",
            transcript,
            height=220,
            disabled=True
        )

        if st.button(
            "Analyze meeting",
            type="primary",
            use_container_width=True
        ):

            if not transcript.strip():
                st.error("The transcript is empty.")

            elif meeting_exists(transcript):
                st.warning(
                    "This exact transcript has already been analyzed. "
                    "Edit it or upload a different one."
                )

            else:

                try:

                    with st.spinner(
                        "MeetFlow is analyzing the meeting with local AI..."
                    ):

                        extraction = extract_meeting(transcript)

                        report = detect_conflicts(
                            extraction.decisions
                        )

                        create_pending_reviews(
                            report,
                            extraction.decisions,
                            extraction.meeting_title
                        )

                        save_extraction(
                            extraction,
                            report
                        )

                        record_meeting(
                            extraction.meeting_title,
                            transcript
                        )

                        st.session_state["last_analysis"] = {
                            "extraction": extraction,
                            "report": report
                        }

                    st.success("Meeting analysis completed!")

                except Exception as error:
                    st.error("Meeting analysis failed!")
                    st.exception(error)

    if "last_analysis" in st.session_state:

        result = st.session_state["last_analysis"]

        extraction = result["extraction"]
        report = result["report"]

        st.divider()
        st.subheader("Analysis results")

        st.markdown(
            f"**Meeting:** {extraction.meeting_title or 'Untitled'}"
        )

        if extraction.meeting_date:
            st.caption(f"Date: {extraction.meeting_date}")

        tab1, tab2, tab3 = st.tabs(
            ["Decisions", "Action items", "Conflicts"]
        )

        with tab1:

            if extraction.decisions:

                for decision in extraction.decisions:

                    with st.container(border=True):

                        st.markdown(f"**{decision.description}**")

                        st.caption(
                            f"Speaker: {decision.speaker or 'Unknown'}"
                        )

                        st.info(
                            f"Evidence: {decision.source_quote}"
                        )

            else:
                st.info("No confirmed decisions extracted.")

        with tab2:

            if extraction.action_items:

                for action in extraction.action_items:

                    with st.container(border=True):

                        st.markdown(f"**{action.task}**")

                        st.write(
                            f"Owner: {action.owner or 'Unassigned'}"
                        )

                        st.write(
                            f"Deadline: {action.deadline or 'Not specified'}"
                        )

                        st.caption(
                            f"Evidence: {action.source_quote}"
                        )

            else:
                st.info("No action items extracted.")

        with tab3:

            if report.findings:

                for finding in report.findings:

                    with st.container(border=True):

                        st.markdown(
                            f"**{finding.status.upper()}**"
                        )

                        st.write(
                            f"Previous: {finding.previous_decision}"
                        )

                        st.write(
                            f"New: {finding.new_decision}"
                        )

                        st.caption(finding.reason)

            else:
                st.success("No relevant conflicts detected.")


# ==========================================
# DECISIONS PAGE
# ==========================================

elif page == "Decisions":

    st.markdown(
        '<div class="eyebrow">LONG-TERM MEMORY</div>',
        unsafe_allow_html=True
    )

    st.title("Decision memory")

    st.caption(
        "Browse active decisions and historical changes."
    )

    history = get_decision_history()

    if history:

        for decision in history:

            with st.container(border=True):

                if decision["status"] == "active":
                    st.success("ACTIVE")
                else:
                    st.caption(decision["status"].upper())

                description = (
                    decision["decision"]
                    if "decision" in decision.keys()
                    else decision["description"]
                )

                st.markdown(f"### {description}")

                st.write(
                    f"Meeting: {decision['meeting_title'] or 'Unknown'}"
                )

                st.write(
                    f"Speaker: {decision['speaker'] or 'Unknown'}"
                )

                st.caption(
                    f"Evidence: {decision['source_quote'] or 'Unavailable'}"
                )

    else:
        st.info("Your decision memory is empty.")


# ==========================================
# ACTION ITEMS PAGE
# ==========================================

elif page == "Action Items":

    st.markdown(
        '<div class="eyebrow">EXECUTION TRACKER</div>',
        unsafe_allow_html=True
    )

    st.title("Action items")

    st.caption(
        "Manage tasks extracted from your meetings and track their progress."
    )

    current_actions = get_all_actions()

    if current_actions:

        total_tasks = len(current_actions)

        completed_count = sum(
            1 for action in current_actions
            if action["status"] == "completed"
        )

        in_progress_count = sum(
            1 for action in current_actions
            if action["status"] == "in_progress"
        )

        pending_count = sum(
            1 for action in current_actions
            if action["status"] in ("pending", "exported")
        )

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Total tasks", total_tasks)
        col2.metric("Completed", completed_count)
        col3.metric("In progress", in_progress_count)
        col4.metric("Pending", pending_count)

        completion_rate = completed_count / total_tasks

        st.progress(completion_rate)

        st.caption(
            f"{round(completion_rate * 100)}% of all tasks completed"
        )

        st.divider()
        st.subheader("Update task status")

        status_options = [
            "pending",
            "in_progress",
            "completed",
            "cancelled",
            "exported"
        ]

        status_labels = {
            "pending": "Pending",
            "in_progress": "In Progress",
            "completed": "Completed",
            "cancelled": "Cancelled",
            "exported": "Exported to Trello"
        }

        for action in current_actions:

            current_status = action["status"] or "pending"

            if current_status not in status_options:
                current_status = "pending"

            with st.container(border=True):

                st.markdown(f"**{action['task']}**")

                col1, col2 = st.columns(2)

                with col1:

                    st.caption(
                        f"Owner: {action['owner'] or 'Unassigned'}"
                    )

                    st.caption(
                        f"Deadline: {action['deadline'] or 'Not specified'}"
                    )

                with col2:

                    st.caption(
                        f"Meeting: {action['meeting_title'] or 'Unknown'}"
                    )

                    if action["trello_card_id"]:
                        st.caption("Trello card linked")

                selected_status = st.selectbox(
                    "Task status",
                    options=status_options,
                    index=status_options.index(current_status),
                    format_func=lambda value: status_labels[value],
                    key=f"action_status_{action['id']}"
                )

                if st.button(
                    "Save status",
                    key=f"save_action_status_{action['id']}",
                    use_container_width=True
                ):

                    try:

                        update_action_status(
                            action["id"],
                            selected_status
                        )

                        st.session_state.pop(
                            "weekly_digest",
                            None
                        )

                        st.success(
                            f"Task status updated to "
                            f"{status_labels[selected_status]}!"
                        )

                        st.rerun()

                    except Exception as error:
                        st.error("Could not update this task.")
                        st.exception(error)

        st.divider()
        st.subheader("Task overview")

        dataframe = pd.DataFrame([
            {
                "Task": action["task"],
                "Owner": action["owner"] or "Unassigned",
                "Deadline": action["deadline"] or "Not specified",
                "Status": status_labels.get(
                    action["status"],
                    action["status"] or "Pending"
                ),
                "Trello": (
                    "Exported"
                    if action["trello_card_id"]
                    else "Not exported"
                )
            }
            for action in current_actions
        ])

        st.dataframe(
            dataframe,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("No action items found. Analyze a meeting first.")


# ==========================================
# APPROVALS PAGE
# ==========================================

elif page == "Approvals":

    st.markdown(
        '<div class="eyebrow">HUMAN-IN-THE-LOOP CONTROL</div>',
        unsafe_allow_html=True
    )

    st.title("Decision approvals")

    st.caption(
        "Review proposed changes before they enter active memory."
    )

    pending_reviews = get_reviews()

    if not pending_reviews:
        st.success("All caught up! No pending approvals.")

    else:

        for review in pending_reviews:

            with st.container(border=True):

                st.warning(
                    f"REVIEW #{review['id']} · PENDING"
                )

                st.markdown("**Previously agreed decision**")
                st.write(review["previous_decision"])

                st.markdown("**Proposed replacement**")
                st.write(review["new_decision"])

                st.markdown("**Why was this flagged?**")
                st.write(review["reason"])

                if review["source_quote"]:
                    st.caption(
                        f"Meeting evidence: {review['source_quote']}"
                    )

                col1, col2 = st.columns(2)

                with col1:

                    if st.button(
                        "Approve change",
                        key=f"approve_{review['id']}",
                        type="primary",
                        use_container_width=True
                    ):

                        try:
                            approve_review(review["id"])
                            st.success("Decision change approved.")
                            st.rerun()

                        except Exception as error:
                            st.error("Could not approve this change.")
                            st.exception(error)

                with col2:

                    if st.button(
                        "Reject change",
                        key=f"reject_{review['id']}",
                        use_container_width=True
                    ):

                        try:
                            reject_review(review["id"])
                            st.info("Decision change rejected.")
                            st.rerun()

                        except Exception as error:
                            st.error("Could not reject this change.")
                            st.exception(error)


# ==========================================
# TRELLO EXPORT PAGE
# ==========================================

elif page == "Trello Export":

    st.markdown(
        '<div class="eyebrow">EXTERNAL INTEGRATION</div>',
        unsafe_allow_html=True
    )

    st.title("Trello task export")

    st.caption(
        "Review extracted action items and approve which ones "
        "MeetFlow should send to your Trello board."
    )

    st.subheader("Trello connection")

    if st.button("Test Trello connection"):

        try:

            with st.spinner("Connecting to Trello..."):

                member = test_connection()
                board = verify_board()

            st.session_state["trello_connected"] = True
            st.session_state["trello_account"] = member["fullName"]
            st.session_state["trello_board"] = board["name"]

        except Exception as error:

            st.session_state["trello_connected"] = False
            st.error("Trello connection failed.")
            st.exception(error)

    if st.session_state.get("trello_connected"):

        st.success("Trello connected successfully!")

        st.write(
            f"Account: {st.session_state['trello_account']}"
        )

        st.write(
            f"Board: {st.session_state['trello_board']}"
        )

    else:
        st.info(
            "Click 'Test Trello connection' to verify your account."
        )

    st.divider()
    st.subheader("Review tasks")

    current_actions = get_all_actions()

    pending_actions = [
        action for action in current_actions
        if not action["trello_card_id"]
    ]

    exported_actions = [
        action for action in current_actions
        if action["trello_card_id"]
    ]

    col1, col2 = st.columns(2)

    col1.metric("Awaiting export", len(pending_actions))
    col2.metric("Already exported", len(exported_actions))

    if not pending_actions:
        st.success("All action items have been exported!")

    else:

        st.warning(
            "Select the tasks you want to approve for Trello export."
        )

        selected_ids = []

        for action in pending_actions:

            with st.container(border=True):

                selected = st.checkbox(
                    "Approve export",
                    key=f"trello_select_{action['id']}"
                )

                st.markdown(f"**{action['task']}**")

                st.write(
                    f"Owner: {action['owner'] or 'Unassigned'}"
                )

                st.write(
                    f"Deadline: {action['deadline'] or 'Not specified'}"
                )

                st.caption(
                    f"Meeting: {action['meeting_title'] or 'Unknown'}"
                )

                st.caption(
                    f"Evidence: {action['source_quote'] or 'Unavailable'}"
                )

                if selected:
                    selected_ids.append(action["id"])

        st.divider()

        st.write(
            f"**{len(selected_ids)} task(s) selected for export.**"
        )

        st.warning(
            "Clicking the button below will create real cards "
            "in your Trello To Do list."
        )

        if st.button(
            "Approve and create Trello cards",
            type="primary",
            use_container_width=True,
            disabled=(
                not selected_ids
                or not st.session_state.get("trello_connected", False)
            )
        ):

            successful = 0
            failed = 0

            for action_id in selected_ids:

                action = next(
                    (
                        item for item in pending_actions
                        if item["id"] == action_id
                    ),
                    None
                )

                if action is None:
                    continue

                try:

                    card = create_action_card(action)

                    mark_action_exported(
                        action_id,
                        card["id"],
                        card["url"]
                    )

                    successful += 1

                except Exception as error:

                    failed += 1

                    st.error(
                        f"Export failed for task ID {action_id}."
                    )

                    st.exception(error)

            if successful:
                st.success(
                    f"{successful} Trello card(s) created successfully!"
                )

            if failed:
                st.error(
                    f"{failed} task(s) could not be confirmed as exported. "
                    "Check Trello before retrying to avoid duplicate cards."
                )

            st.rerun()

    st.divider()
    st.subheader("Export history")

    if exported_actions:

        for action in exported_actions:

            with st.container(border=True):

                st.success("EXPORTED")
                st.markdown(f"**{action['task']}**")

                st.caption(
                    f"Owner: {action['owner'] or 'Unassigned'}"
                )

                st.link_button(
                    "Open Trello card",
                    action["trello_card_url"],
                    use_container_width=False
                )

    else:
        st.info("No tasks have been exported yet.")


# ==========================================
# DEADLINE REMINDERS PAGE
# ==========================================

elif page == "Deadline Reminders":

    st.markdown(
        '<div class="eyebrow">STAY AHEAD</div>',
        unsafe_allow_html=True
    )

    st.title("Deadline reminders")

    st.caption(
        "Keep track of overdue, due-today, and upcoming action items."
    )

    st.info(
        "MeetFlow checks stored action-item deadlines and creates "
        "each reminder only once per reminder category."
    )

    if st.button(
        "Check deadlines now",
        type="primary",
        use_container_width=True
    ):

        try:

            with st.spinner("Checking action-item deadlines..."):

                results = check_deadline_reminders()

            st.success("Deadline check completed!")

            col1, col2, col3 = st.columns(3)

            col1.metric(
                "New overdue reminders",
                len(results["overdue"])
            )

            col2.metric(
                "Due today",
                len(results["due_today"])
            )

            col3.metric(
                "Upcoming",
                len(results["upcoming"])
            )

            if results["email_sent"]:
                st.success(
                    f"{len(results['email_sent'])} reminder email(s) sent."
                )

            if results["email_failed"]:
                st.error(
                    f"{len(results['email_failed'])} email(s) failed. "
                    "They will be retried on the next check."
                )

                for failure in results["email_failed"]:
                    st.caption(
                        f"{failure['task']} -> {failure['error']}"
                    )

            if results["email_skipped"]:
                st.caption(
                    f"{len(results['email_skipped'])} reminder(s) were not "
                    "emailed (no owner or no registered address)."
                )

            if results["skipped"]:
                st.caption(
                    f"{len(results['skipped'])} task(s) skipped "
                    "because their deadline could not be interpreted."
                )

        except Exception as error:
            st.error("Could not check deadlines.")
            st.exception(error)

    st.divider()
    st.subheader("Reminder history")

    reminders = get_all_reminders()

    if reminders:

        for reminder in reminders:

            with st.container(border=True):

                reminder_type = reminder["reminder_type"]

                if reminder_type == "overdue":
                    st.error("OVERDUE")
                elif reminder_type == "due_today":
                    st.warning("DUE TODAY")
                else:
                    st.info("UPCOMING")

                st.markdown(f"**{reminder['task']}**")
                st.write(reminder["message"])

                st.caption(
                    f"Owner: {reminder['owner'] or 'Unassigned'}"
                    f" · Deadline: {reminder['deadline'] or 'Unknown'}"
                )

                st.caption(
                    f"Reminder created: {reminder['created_at']}"
                    + (
                        f" · Emailed: {reminder['emailed_at']}"
                        if reminder["emailed_at"] else " · Not emailed"
                    )
                )

    else:
        st.info(
            "No reminders yet. Click 'Check deadlines now' "
            "to generate your first reminders."
        )


# ==========================================
# WEEKLY INDIVIDUAL DIGEST PAGE
# ==========================================

elif page == "Weekly Digest":

    st.markdown(
        '<div class="eyebrow">WEEKLY REPORTING</div>',
        unsafe_allow_html=True
    )

    st.title("Weekly individual digest")

    st.caption(
        "A personal breakdown of responsibilities, progress, "
        "deadlines, and meeting decisions."
    )

    if st.button(
        "Generate weekly digest",
        type="primary",
        use_container_width=True
    ):

        try:

            with st.spinner("Preparing individual reports..."):

                digest = generate_weekly_digests()

            st.session_state["weekly_digest"] = digest
            st.success("Weekly digest generated!")

        except Exception as error:
            st.error("Could not generate the digest.")
            st.exception(error)

    if "weekly_digest" in st.session_state:

        digest = st.session_state["weekly_digest"]

        st.caption(
            f"Generated: {digest['generated_on']} · "
            f"Next 7 days through: {digest['period_end']}"
        )

        people = digest["people"]

        if not people:
            st.info(
                "No assigned people or action items found yet. "
                "Analyze a meeting with action items first."
            )

        else:

            st.divider()

            selected_person = st.selectbox(
                "Select a person",
                list(people.keys())
            )

            person = people[selected_person]

            st.subheader(f"Report for {selected_person}")

            col1, col2, col3, col4 = st.columns(4)

            col1.metric("Total tasks", len(person["tasks"]))
            col2.metric("Completed", len(person["completed"]))
            col3.metric("Pending", len(person["pending"]))
            col4.metric("Overdue", len(person["overdue"]))

            st.progress(person["completion_rate"] / 100)

            st.caption(
                f"Task completion: {person['completion_rate']}%"
            )

            st.divider()
            st.subheader("Overdue tasks")

            if person["overdue"]:

                for task in person["overdue"]:

                    with st.container(border=True):

                        st.error("OVERDUE")
                        st.markdown(f"**{task['task']}**")

                        st.caption(
                            f"Deadline: {task['deadline']} · "
                            f"Meeting: {task['meeting']}"
                        )

            else:
                st.success("No overdue tasks.")

            st.divider()
            st.subheader("Upcoming tasks")

            if person["upcoming"]:

                for task in person["upcoming"]:

                    with st.container(border=True):

                        st.info("UPCOMING")
                        st.markdown(f"**{task['task']}**")

                        st.caption(
                            f"Deadline: {task['deadline']} · "
                            f"Meeting: {task['meeting']}"
                        )

            else:
                st.write("No tasks due in the next seven days.")

            st.divider()
            st.subheader("All assigned tasks")

            task_dataframe = pd.DataFrame([
                {
                    "Task": task["task"],
                    "Deadline": task["deadline"],
                    "Status": task["status"],
                    "Meeting": task["meeting"]
                }
                for task in person["tasks"]
            ])

            if person["tasks"]:

                st.dataframe(
                    task_dataframe,
                    use_container_width=True,
                    hide_index=True
                )

            else:
                st.info("No tasks assigned.")

            st.divider()
            st.subheader("Meeting decisions")

            if person["decisions"]:

                for decision in person["decisions"]:

                    with st.container(border=True):

                        st.markdown(
                            f"**{decision['decision']}**"
                        )

                        st.caption(
                            f"Meeting: {decision['meeting']}"
                        )

            else:
                st.info(
                    "No decisions attributed to this person."
                )

            st.divider()

            csv_data = (
                task_dataframe.to_csv(index=False)
                if person["tasks"]
                else ""
            )

            if csv_data:

                st.download_button(
                    "Download personal task report (CSV)",
                    data=csv_data,
                    file_name=(
                        f"meetflow_digest_"
                        f"{selected_person.replace(' ', '_')}.csv"
                    ),
                    mime="text/csv",
                    use_container_width=True
                )


# ==========================================
# EMAIL DIRECTORY PAGE
# ==========================================

elif page == "Email Directory":

    st.markdown(
        '<div class="eyebrow">TEAM COMMUNICATION</div>',
        unsafe_allow_html=True
    )

    st.title("Owner email directory")

    st.caption(
        "Connect task owners with their email addresses "
        "so MeetFlow knows where to send reminders."
    )

    st.write("")

    st.subheader("Register a team member")

    with st.container(border=True):

        with st.form("owner_email_form"):

            owner_name = st.text_input(
                "Owner name",
                placeholder="e.g. Sarah"
            )

            owner_email = st.text_input(
                "Email address",
                placeholder="e.g. sarah@example.com"
            )

            submitted = st.form_submit_button(
                "Save email address",
                type="primary",
                use_container_width=True
            )

            if submitted:

                owner_name = owner_name.strip()
                owner_email = owner_email.strip()

                if not owner_name:
                    st.error("Please enter the owner's name.")

                elif (
                    not owner_email
                    or "@" not in owner_email
                    or "." not in owner_email.split("@")[-1]
                    or " " in owner_email
                ):
                    st.error("Please enter a valid email address.")

                else:

                    try:

                        save_owner_email(
                            owner_name,
                            owner_email
                        )

                        st.success(
                            f"Email address saved for {owner_name}!"
                        )

                        st.rerun()

                    except Exception as error:

                        st.error("Could not save this email address.")
                        st.exception(error)

    st.divider()

    st.subheader("Registered team members")

    owner_emails = get_all_owner_emails()

    col1, col2 = st.columns(2)

    col1.metric("Registered members", len(owner_emails))
    col2.metric("Available email destinations", len(owner_emails))

    if owner_emails:

        for member in owner_emails:

            with st.container(border=True):

                col1, col2 = st.columns([4, 1])

                with col1:

                    st.markdown(f"**{member['owner']}**")
                    st.write(member["email"])

                    st.caption(
                        f"Last updated: {member['updated_at']}"
                    )

                with col2:

                    if st.button(
                        "Delete",
                        key=f"delete_owner_{member['owner']}",
                        use_container_width=True
                    ):

                        try:

                            delete_owner_email(member["owner"])

                            st.success(
                                f"Removed {member['owner']} "
                                "from the email directory."
                            )

                            st.rerun()

                        except Exception as error:

                            st.error("Could not remove this member.")
                            st.exception(error)

    else:

        st.info(
            "No team members registered yet. "
            "Add your first owner above."
        )

    st.divider()

    st.subheader("How email matching works")

    st.markdown("""
    - MeetFlow reads the owner assigned to an action item.
    - It searches this directory for that owner's email address.
    - If an email address exists, the reminder can be sent there.
    - If no address exists, the reminder will be skipped.
    - Registering the same owner again updates their existing address.
    """)

    st.info(
        "Reminder emails are sent from the Gmail account in your .env "
        "file whenever you click 'Check deadlines now'. If a send fails, "
        "or you add an address later, the next check tries again."
    )
