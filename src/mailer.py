import os
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def _split_recipients(raw: str):
    if not raw:
        return []
    parts = re.split(r"[;,\" "]+", raw)
    return [p.strip() for p in parts if p.strip()]

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
        subject = f"\ud83d\udcca Company Intelligence Report — {datetime.now().strftime('%B %d, %Y')}"

    if logger:
        logger.info(f"Preparing email | sender={sender} recipients={len(recipients)} dry_run={dry_run}")

    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html", "utf-8"))

    if dry_run:
        if logger:
            logger.info(f"[DRY_RUN] Would send email to {recipients} with subject: {subject}")
        return

    # Gmail SMTP over TLS (port 587). Requires App Password.
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, pwd)
        server.send_message(msg)

    if logger:
        logger.info(f"Email sent to {len(recipients)} recipients")
