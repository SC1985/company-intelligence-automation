import os
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import make_msgid, formataddr

_SURROGATE_RE = re.compile(r'[\ud800-\udfff]')

def _split_recipients(raw: str):
    if not raw:
        return []
    parts = re.split(r"[;,\s]+", raw)
    return [p.strip() for p in parts if p.strip()]

def _clean_subject(s: str) -> str:
    s = (s or "").replace("\r", " ").replace("\n", " ")
    s = " ".join(s.split())
    s = _SURROGATE_RE.sub("", s)
    return s.strip()

def validate_env():
    sender = os.getenv("SENDER_EMAIL")
    sender_name = os.getenv("SENDER_NAME", "").strip()
    reply_to = os.getenv("REPLY_TO", "").strip()
    pwd = os.getenv("SENDER_PASSWORD")
    recipients = _split_recipients(os.getenv("RECIPIENT_EMAILS", ""))
    admin_emails = _split_recipients(os.getenv("ADMIN_EMAILS", ""))
    copy_sender = os.getenv("COPY_SENDER", "true").lower() == "true"
    smtp_debug = os.getenv("SMTP_DEBUG", "false").lower() == "true"

    missing = []
    if not sender:
        missing.append("SENDER_EMAIL")
    if not pwd:
        missing.append("SENDER_PASSWORD")
    if not recipients:
        missing.append("RECIPIENT_EMAILS")

    return {
        "sender": sender,
        "sender_name": sender_name,
        "reply_to": reply_to,
        "pwd": pwd,
        "recipients": recipients,
        "admin_emails": admin_emails,
        "copy_sender": copy_sender,
        "smtp_debug": smtp_debug,
        "missing": missing
    }

def send_html_email(html: str, subject: str = None, logger=None) -> None:
    cfg = validate_env()
    missing = cfg["missing"]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    dry_run = os.getenv("DRY_RUN", "").lower() == "true"

    if subject is None:
        subject = f"Weekly Company Intelligence Report — {datetime.now().strftime('%B %d, %Y')}"
    subject = _clean_subject(subject)

    sender_disp = formataddr((cfg["sender_name"] or "", cfg["sender"]))
    to_header = ", ".join(cfg["recipients"])

    if logger:
        logger.info(f"Preparing email | sender={cfg['sender']} recipients={len(cfg['recipients'])} dry_run={dry_run}")

    msg = MIMEMultipart("alternative")
    msg["From"] = sender_disp
    msg["To"] = to_header
    msg["Subject"] = str(Header(subject, "utf-8"))
    if cfg["reply_to"]:
        msg["Reply-To"] = cfg["reply_to"]
    # Deterministic Message-ID (based on sender's domain)
    try:
        domain = cfg["sender"].split("@", 1)[1]
    except Exception:
        domain = None
    msg_id = make_msgid(domain=domain)
    msg["Message-ID"] = msg_id

    # Body: provide HTML and a minimal text alternative
    text_alt = re.sub(r"<[^>]+>", " ", html or "")
    text_alt = re.sub(r"\s+", " ", text_alt).strip() or "This email contains an HTML report."
    msg.attach(MIMEText(text_alt, "plain", "utf-8"))
    msg.attach(MIMEText(html or "", "html", "utf-8"))

    if dry_run:
        if logger:
            logger.info(f"[DRY_RUN] Would send email to {cfg['recipients']} (plus copy/admin if enabled) "
                        f"| subject: {subject} | message-id: {msg_id}")
        return

    # Build final recipient list (envelope):
    to_addrs = list(cfg["recipients"])
    if cfg["copy_sender"] and cfg["sender"] not in to_addrs:
        to_addrs.append(cfg["sender"])
    for a in cfg["admin_emails"]:
        if a not in to_addrs:
            to_addrs.append(a)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        if cfg["smtp_debug"]:
            server.set_debuglevel(1)  # print SMTP conversation to stdout
        server.starttls()
        server.login(cfg["sender"], cfg["pwd"])
        refused = server.sendmail(cfg["sender"], to_addrs, msg.as_string())
        if logger:
            logger.info(f"SMTP refused recipients map: {refused!r} | message-id: {msg_id}")
        if refused:
            raise RuntimeError(f"SMTP refused some recipients: {refused}")
        if logger:
            logger.info(f"Email handed to SMTP for {len(to_addrs)} recipient(s). "
                        f"Primary To: {len(cfg['recipients'])}, "
                        f"Copied to sender: {cfg['copy_sender']}, Admins: {len(cfg['admin_emails'])}")
