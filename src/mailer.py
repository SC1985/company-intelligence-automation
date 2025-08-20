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

def _mask_local(local: str):
    if not local:
        return ""
    if len(local) <= 3:
        return "*" * len(local)
    return local[:2] + "***" + local[-1:]

def _mask_email(addr: str):
    if not addr or "@" not in addr:
        return "***"
    local, domain = addr.split("@", 1)
    return f"{_mask_local(local)}@{domain}"

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
    copy_sender = os.getenv("COPY_SENDER", "false").lower() == "true"  # default false in v5
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

    # Logging: show masked addresses
    masked_to = [_mask_email(r) for r in cfg["recipients"]]
    masked_admins = [_mask_email(a) for a in cfg["admin_emails"]]
    if logger:
        eq_sender = any(r.lower() == cfg["sender"].lower() for r in cfg["recipients"])
        logger.info(f"Recipients(masked)={masked_to} | Admins(masked)={masked_admins} | any_to_equals_sender={eq_sender} | copy_sender={cfg['copy_sender']} | dry_run={dry_run}")

    msg = MIMEMultipart("alternative")
    msg["From"] = sender_disp
    msg["To"] = ", ".join(cfg["recipients"])
    try:
        msg["Subject"] = str(Header(subject, "utf-8"))
    except UnicodeEncodeError:
        safe_subject = subject.encode("ascii", "ignore").decode("ascii") or "Weekly Company Intelligence Report"
        msg["Subject"] = str(Header(safe_subject, "utf-8"))
    if cfg["reply_to"]:
        msg["Reply-To"] = cfg["reply_to"]

    # Add trace headers
    run_id = os.getenv("GITHUB_RUN_ID", "")
    run_attempt = os.getenv("GITHUB_RUN_ATTEMPT", "")
    run_number = os.getenv("GITHUB_RUN_NUMBER", "")
    sha = os.getenv("GITHUB_SHA", "")[:12]
    domain_list = sorted({addr.split("@",1)[1] for addr in cfg["recipients"] if "@" in addr})
    msg["Message-ID"] = make_msgid(domain=(cfg["sender"].split("@",1)[1] if "@" in cfg["sender"] else None))
    msg["X-GitHub-Run-ID"] = run_id
    msg["X-GitHub-Run-Attempt"] = run_attempt
    msg["X-GitHub-Run-Number"] = run_number
    msg["X-Recipient-Domains"] = ",".join(domain_list)
    msg["X-Report-Timestamp"] = datetime.utcnow().isoformat() + "Z"

    # Body parts
    import re as _re
    text_alt = _re.sub(r"<[^>]+>", " ", html or "")
    text_alt = _re.sub(r"\s+", " ", text_alt).strip() or "This email contains an HTML report."
    msg.attach(MIMEText(text_alt, "plain", "utf-8"))
    msg.attach(MIMEText(html or "", "html", "utf-8"))

    if dry_run:
        if logger:
            logger.info(f"[DRY_RUN] Would send. Subject='{subject}' | To(masked)={masked_to} | Admins(masked)={masked_admins}")
        return

    # Build envelope recipients with dedupe
    to_addrs = list(dict.fromkeys(cfg["recipients"]))  # preserve order, drop dups
    if cfg["copy_sender"] and cfg["sender"] not in to_addrs:
        to_addrs.append(cfg["sender"])
    for a in cfg["admin_emails"]:
        if a not in to_addrs:
            to_addrs.append(a)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        if cfg["smtp_debug"]:
            server.set_debuglevel(1)
        server.starttls()
        server.login(cfg["sender"], cfg["pwd"])
        refused = server.sendmail(cfg["sender"], to_addrs, msg.as_string())
        if logger:
            masked_env = [_mask_email(x) for x in to_addrs]
            logger.info(f"Envelope recipients(masked)={masked_env}")
            logger.info(f"SMTP refused recipients map: {refused!r}")
        if refused:
            raise RuntimeError(f"SMTP refused some recipients: {refused}")
        if logger:
            logger.info(f"Email handed to SMTP for {len(to_addrs)} recipient(s).")
