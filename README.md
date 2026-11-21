# MeetFlow

**Meetings into momentum.** MeetFlow reads a meeting transcript with a
*local* AI model (Ollama), pulls out the decisions and action items,
warns you when a new decision contradicts an old one, and then helps
the team follow through with Trello cards and email reminders.

Nothing about your meetings is sent to a cloud AI service: the language
model runs on your own computer.

## Features

- **Meeting analysis** – upload a `.txt` transcript and get decisions and
  action items, each with the exact quote that supports it.
- **Decision memory** – every decision is stored. When a new meeting
  contradicts an earlier one (for example the launch date moves), MeetFlow
  flags it instead of silently overwriting it.
- **Human approval** – a flagged change waits on the *Approvals* page.
  Approve it and the old decision becomes "superseded" and the new one
  becomes active. Reject it and nothing changes.
- **Action tracker** – owners, deadlines, statuses and progress.
- **Trello export** – you choose which tasks become real cards (with due
  dates).
- **Deadline reminders** – overdue, due-today and upcoming (next 2 days)
  tasks, emailed through Gmail to registered owners. Failed emails are
  retried on the next check.
- **Weekly digest** – a per-person report with a CSV download.
- Deadlines like `November 24`, `Friday`, `tomorrow` or `in 3 days` are
  understood and converted to real dates.

## Setup

1. **Install Ollama** from <https://ollama.com> and download the model:

   ```bash
   ollama pull llama3.2:3b
   ```

2. **Create a virtual environment and install the packages**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   source .venv/bin/activate       # Mac / Linux
   pip install -r requirements.txt
   ```

3. **Add your keys (optional).** Copy `.env.example` to `.env` and fill it
   in. Trello and Gmail are only needed for exports and reminder emails.

4. **Run the app** (make sure Ollama is running)

   ```bash
   streamlit run app.py
   ```

Try it with the transcripts in `sample_data/`. `meeting_02.txt` changes a
decision from `meeting_01.txt`, so it demonstrates conflict detection.

## Tests

The automated tests need no internet, Ollama, Trello or Gmail:

```bash
python -m unittest discover -s tests -t . -v
```

The `test_*.py` files in the project root are older **manual scripts** that
talk to Ollama and Trello for real (`test_trello_create.py` creates a real
card). Run them one at a time, on purpose.

## Project layout

```
app.py                 Streamlit user interface
core/
  extractor.py         transcript -> decisions + action items (Ollama)
  conflict.py          new decisions vs. stored decisions (Ollama)
  approval.py          human approval of decision changes
  memory.py            decision and action memory
  reminders.py         overdue / due today / upcoming + emails
  digest.py            weekly per-person report
  dates.py             "Friday", "November 24" -> real dates
  validation.py        guards against invented IDs from the model
database/db.py         all SQLite access (data/meetflow.db)
integrations/          Trello and Gmail
tests/                 offline automated tests
sample_data/           example transcripts
```

## Good to know

- Data is stored in `data/meetflow.db` and is ignored by Git.
- Small local models make mistakes. That is why MeetFlow keeps the source
  quote next to every item and asks a human to approve decision changes.
- Never commit `.env`. If a key ever leaks, regenerate it.
