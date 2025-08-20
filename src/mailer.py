import os
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header

def _split_recipients(raw: str):
    if not raw:
        return []
    # Accept comma, semicolon, or whitespace as delimiters
    parts = re.split(r"[;,\s]+", raw)
    return [p.strip() for p in parts if p.strip()]

def _clean_subject(s: str) -> str:
    # Prevent header injection and normalize whitespace
    return " ".join((s or "").replace("\r", " ").replace("\n", " ").split())

def validate_env():
    sender = os.getenv("SENDER_EMAIL")
    pwd = os.getenv("SENDER_PASSWORD")
    recipients = _split_recipients(os.getenv("RECIPIENT_EMAILS", ""))
    missing = []
    if not sender:
        missing.append("SENDER_EMAIL")
    if not pwd:
        missing.append("SENDER_PASSWORD")
    if not recipients:
        missing.append("RECIPIENT_EMAILS")
    return sender, pwd, recipients, missing

def send_html_email(html: str, subject: str = None, logger=None) -> None:
    sender, pwd, recipients, missing = validate_env()
    dry_run = os.getenv("DRY_RUN", "").lower() == "true"

    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    if subject is None:
        subject = f"📊 Company Intelligence Report — {datetime.now().strftime('%B %d, %Y')}"
    subject = _clean_subject(subject)

    if logger:
        logger.info(f"Preparing email | sender={sender} recipients={len(recipients)} dry_run={dry_run}")

    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    # Encode non-ASCII safely so the SMTP generator doesn't choke
    msg["Subject"] = str(Header(subject, "utf-8"))

    # Body
    msg.attach(MIMEText(html, "html", "utf-8"))

    if dry_run:
        if logger:
            logger.info(f"[DRY_RUN] Would send email to {recipients} with subject: {subject}")
        return

    # Gmail SMTP over TLS (port 587). Requires App Password.
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, pwd)
        try:
            server.send_message(msg)
        except UnicodeEncodeError:
            # Absolute fallback: strip emojis/non-ASCII from Subject and retry
            safe_subject = subject.encode("ascii", "ignore").decode("ascii") or "Weekly Company Intelligence Report"
            msg.replace_header("Subject", str(Header(safe_subject, "utf-8")))
            server.send_message(msg)

    if logger:
        logger.info(f"Email sent to {len(recipients)} recipients")
