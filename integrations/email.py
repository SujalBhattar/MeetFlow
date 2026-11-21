
import os
import smtplib

from email.message import EmailMessage
from dotenv import load_dotenv


load_dotenv()

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")


def send_reminder_email(recipient, subject, message):

    if not EMAIL_ADDRESS:
        raise ValueError(
            "EMAIL_ADDRESS is missing from your .env file."
        )

    if not EMAIL_APP_PASSWORD:
        raise ValueError(
            "EMAIL_APP_PASSWORD is missing from your .env file."
        )

    if not recipient:
        raise ValueError("Recipient email address is missing.")

    email = EmailMessage()

    email["From"] = EMAIL_ADDRESS
    email["To"] = recipient
    email["Subject"] = subject

    email.set_content(
        f"""
Hello,

This is an automated reminder from MeetFlow.

{message}

--------------------------------
MeetFlow
Meeting-to-Execution Agent
        """
    )

    try:
        with smtplib.SMTP_SSL(
            SMTP_SERVER,
            SMTP_PORT,
            timeout=20
        ) as server:

            server.login(
                EMAIL_ADDRESS,
                EMAIL_APP_PASSWORD
            )

            server.send_message(email)

        return True

    except smtplib.SMTPAuthenticationError:
        raise RuntimeError(
            "Gmail authentication failed. "
            "Check your email address and App Password."
        )

    except smtplib.SMTPException as error:
        raise RuntimeError(
            f"Email delivery failed: {error}"
        )
