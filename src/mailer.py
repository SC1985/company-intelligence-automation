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

def _generate_dynamic_subject() -> str:
    """Generate engaging, dynamic subject lines with variety."""
    now = datetime.now()
    current_hour = now.hour
    day_of_week = now.strftime("%A")
    date_formatted = now.strftime("%m/%d")
    
    # Time-based prefixes
    if 5 <= current_hour < 12:
        time_emoji = "🌅"
        time_context = "Morning"
    elif 12 <= current_hour < 17:
        time_emoji = "☀️"
        time_context = "Midday"
    elif 17 <= current_hour < 21:
        time_emoji = "🌆"
        time_context = "Evening"
    else:
        time_emoji = "🌙"
        time_context = "Late"
    
    # Dynamic subject templates
    subject_templates = [
        f"{time_emoji} Intelligence Digest • {date_formatted} Market Pulse",
        f"📊 Strategic Brief • {day_of_week} {time_context} Edition",
        f"🎯 Portfolio Intelligence • {date_formatted} Key Signals", 
        f"⚡ Market Update • {time_context} Intelligence Summary",
        f"🔍 Intelligence Digest • {date_formatted} Strategic Insights",
        f"📈 {day_of_week} Brief • Portfolio & Market Intelligence",
        f"🚀 Strategic Update • {date_formatted} Investment Intelligence",
        f"💡 Market Intelligence • {time_context} Digest {date_formatted}"
    ]
    
    # Rotate based on day of year for consistency but variety
    template_index = now.timetuple().tm_yday % len(subject_templates)
    return subject_templates[template_index]

def _extract_preview_from_html(html: str) -> str:
    """Extract compelling preview text from email HTML."""
    if not html:
        return "Strategic market intelligence and portfolio insights"
    
    # Look for hero article content first
    hero_match = re.search(r'<div[^>]*font-weight:700[^>]*font-size:22px[^>]*>(.*?)</div>', html, re.S | re.I)
    if hero_match:
        hero_title = re.sub(r'<[^>]+>', '', hero_match.group(1)).strip()
        if hero_title and len(hero_title) > 20:
            return f"{hero_title[:100]}..."
    
    # Look for any significant text content
    text_content = re.sub(r'<[^>]+>', ' ', html)
    text_content = re.sub(r'\s+', ' ', text_content).strip()
    
    # Find meaningful sentences (not just timestamps or metadata)
    sentences = [s.strip() for s in text_content.split('.') if len(s.strip()) > 20]
    meaningful_sentences = [s for s in sentences if not any(word in s.lower() for word in 
                           ['data as of', 'generated', 'you\'re receiving', 'unsubscribe', 'copyright'])]
    
    if meaningful_sentences:
        preview = meaningful_sentences[0]
        return f"{preview[:120]}..." if len(preview) > 120 else preview
    
    # Fallback to dynamic preview
    return _generate_dynamic_preview()

def _generate_dynamic_preview() -> str:
    """Generate compelling preview text that encourages opens."""
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    
    preview_options = [
        f"Market intelligence update {current_time} • Key movements, sentiment analysis & strategic signals",
        f"Portfolio pulse check {current_time} • Performance insights, news highlights & market momentum", 
        f"Strategic briefing {current_time} • Top movers, sector analysis & breaking developments",
        f"Intelligence summary {current_time} • Market data, portfolio updates & strategic opportunities",
        f"Market snapshot {current_time} • Real-time insights, news synthesis & investment signals"
    ]
    
    # Rotate preview based on day to maintain freshness
    preview_index = now.timetuple().tm_yday % len(preview_options)
    return preview_options[preview_index]

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

    # 🔥 NEW: Enhanced subject line generation
    if subject is None:
        subject = _generate_dynamic_subject()
    subject = _clean_subject(subject)

    # 🔥 NEW: Enhanced sender display name
    sender_display_name = cfg["sender_name"] or "Intelligence Digest"
    sender_disp = formataddr((sender_display_name, cfg["sender"]))

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
        safe_subject = subject.encode("ascii", "ignore").decode("ascii") or "Intelligence Digest"
        msg["Subject"] = str(Header(safe_subject, "utf-8"))
    
    if cfg["reply_to"]:
        msg["Reply-To"] = cfg["reply_to"]

    # 🔥 NEW: Enhanced email headers for better inbox display
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
    
    # Enhanced headers for better deliverability & inbox display
    msg["List-Unsubscribe"] = "<mailto:unsubscribe@example.com>"
    msg["X-Mailer"] = "Intelligence Digest v2.0"
    msg["X-Priority"] = "3"
    msg["Importance"] = "Normal"
    msg["X-Auto-Response-Suppress"] = "OOF, DR, RN, NRN, AutoReply"

    # Body parts with enhanced preview text
    preview_text = _extract_preview_from_html(html)
    
    # Create enhanced plain text version with preview
    import re as _re
    text_alt = _re.sub(r"<[^>]+>", " ", html or "")
    text_alt = _re.sub(r"\s+", " ", text_alt).strip()
    
    if not text_alt:
        text_alt = f"{preview_text}\n\nThis email contains your Intelligence Digest with market data, portfolio insights, and strategic analysis."
    
    # Enhanced HTML with better preview text handling
    if html and "display:none" not in html:
        # Add preview text if not already present
        html = html.replace("<body", f'<div style="display:none;font-size:1px;color:#0b0c10;line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;">{preview_text}</div><body', 1)
    
    msg.attach(MIMEText(text_alt, "plain", "utf-8"))
    msg.attach(MIMEText(html or "", "html", "utf-8"))

    if dry_run:
        if logger:
            logger.info(f"[DRY_RUN] Would send. Subject='{subject}' | Preview='{preview_text[:50]}...' | To(masked)={masked_to} | Admins(masked)={masked_admins}")
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
            logger.info(f"Email sent with subject: '{subject}' and preview: '{preview_text[:50]}...'")
        if refused:
            raise RuntimeError(f"SMTP refused some recipients: {refused}")
        if logger:
            logger.info(f"Email handed to SMTP for {len(to_addrs)} recipient(s).")
