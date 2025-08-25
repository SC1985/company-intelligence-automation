import os
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import make_msgid, formataddr
import hashlib
import socket

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
    """Enhanced subject line cleaning with better character handling."""
    s = (s or "").replace("\r", " ").replace("\n", " ")
    s = " ".join(s.split())
    s = _SURROGATE_RE.sub("", s)
    # Remove problematic characters that might trigger spam filters
    s = re.sub(r'[^\w\s\-\.\(\)\[\]!?,&$€£¥₹•→←↑↓★☆⭐🔥⚡📊📈💡🎯🌅☀️🌆🌙]+', ' ', s)
    return s.strip()

def _generate_enhanced_subject() -> str:
    """Generate sophisticated, engagement-optimized subject lines."""
    now = datetime.now()
    current_hour = now.hour
    day_of_week = now.strftime("%A")
    date_formatted = now.strftime("%m/%d")
    
    # Time-aware context
    if 5 <= current_hour < 12:
        time_emoji = "🌅"
        time_context = "Morning"
        urgency_level = "medium"
    elif 12 <= current_hour < 17:
        time_emoji = "📊"
        time_context = "Midday"
        urgency_level = "high"
    elif 17 <= current_hour < 21:
        time_emoji = "🌆"
        time_context = "Evening"
        urgency_level = "medium"
    else:
        time_emoji = "🌙"
        time_context = "Late"
        urgency_level = "low"
    
    # Enhanced subject templates with psychological triggers
    subject_templates = [
        # Action-oriented
        f"{time_emoji} Intelligence Alert • {date_formatted} Market Signals",
        f"⚡ Breaking: {day_of_week} Portfolio Intelligence • {date_formatted}",
        f"🔥 {time_context} Brief • Critical Updates & Market Pulse",
        
        # Value-focused  
        f"💡 Strategic Intelligence • {date_formatted} Investment Insights",
        f"🎯 Portfolio Digest • {day_of_week} Performance & News",
        f"📈 Market Intelligence • {time_context} Edition {date_formatted}",
        
        # Urgency-driven
        f"⚡ LIVE: {time_context} Market Pulse • Key Movements & Signals",
        f"🚀 Intelligence Update • {date_formatted} Strategic Opportunities",
        
        # Professional
        f"📊 Executive Brief • {day_of_week} {time_context} Intelligence",
        f"💼 Strategic Update • {date_formatted} Portfolio & Market Analysis"
    ]
    
    # Select based on day and urgency
    base_index = now.timetuple().tm_yday % len(subject_templates)
    
    # Adjust for urgency level
    if urgency_level == "high":
        # Prefer action-oriented subjects during peak hours
        urgent_subjects = [s for s in subject_templates if any(word in s for word in ["Alert", "Breaking", "LIVE", "Critical"])]
        if urgent_subjects:
            return urgent_subjects[base_index % len(urgent_subjects)]
    
    return subject_templates[base_index]

def _extract_hero_content(html: str) -> dict:
    """Enhanced hero content extraction with multiple fallback strategies."""
    if not html:
        return {"title": "", "description": "", "source": ""}
    
    hero_content = {"title": "", "description": "", "source": ""}
    
    # Strategy 1: Look for hero container patterns from render_email.py
    hero_patterns = [
        # Main hero container
        r'<table[^>]*background[^>]*linear-gradient[^>]*>.*?<td[^>]*padding[^>]*>.*?<div[^>]*font-weight:700[^>]*font-size:24px[^>]*>(.*?)</div>(.*?)</td>.*?</table>',
        
        # Alternative hero patterns
        r'<div[^>]*class="hero[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*background[^>]*#111827[^>]*>.*?<div[^>]*font-size:2[24]px[^>]*>(.*?)</div>(.*?)</div>',
    ]
    
    for pattern in hero_patterns:
        matches = re.finditer(pattern, html, re.S | re.I)
        for match in matches:
            # Extract title
            title_html = match.group(1)
            title_link_match = re.search(r'<a[^>]*>(.*?)</a>', title_html, re.S | re.I)
            if title_link_match:
                hero_content["title"] = re.sub(r'<[^>]+>', '', title_link_match.group(1)).strip()
            else:
                hero_content["title"] = re.sub(r'<[^>]+>', '', title_html).strip()
            
            # Extract description from remaining content
            if len(match.groups()) > 1:
                remaining_content = match.group(2)
                # Look for description in div tags
                desc_match = re.search(r'<div[^>]*color[^>]*#d1d5db[^>]*>(.*?)</div>', remaining_content, re.S | re.I)
                if desc_match:
                    hero_content["description"] = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
                
                # Look for source information
                source_match = re.search(r'<span[^>]*font-weight:500[^>]*>(.*?)</span>', remaining_content, re.S | re.I)
                if source_match:
                    hero_content["source"] = re.sub(r'<[^>]+>', '', source_match.group(1)).strip()
            
            if hero_content["title"] and len(hero_content["title"]) > 10:
                break
    
    # Strategy 2: Look for any prominent headlines in the content
    if not hero_content["title"]:
        headline_patterns = [
            r'<h[12][^>]*>(.*?)</h[12]>',
            r'<div[^>]*font-size:2[0-9]px[^>]*font-weight:[67]00[^>]*>(.*?)</div>',
            r'<a[^>]*style="[^"]*font-size:[2-9][0-9]px[^"]*"[^>]*>(.*?)</a>',
        ]
        
        for pattern in headline_patterns:
            matches = re.finditer(pattern, html, re.S | re.I)
            for match in matches:
                title_candidate = re.sub(r'<[^>]+>', '', match.group(1)).strip()
                # Skip generic titles
                if (title_candidate and 
                    len(title_candidate) > 15 and 
                    len(title_candidate) < 200 and
                    'intelligence digest' not in title_candidate.lower() and
                    not title_candidate.isdigit()):
                    hero_content["title"] = title_candidate
                    break
            if hero_content["title"]:
                break
    
    # Strategy 3: Extract description from content near the title
    if hero_content["title"] and not hero_content["description"]:
        # Look for content after the title
        title_escaped = re.escape(hero_content["title"])
        content_after_title = re.search(
            rf'{title_escaped}.*?<div[^>]*>(.*?)</div>',
            html, re.S | re.I
        )
        if content_after_title:
            desc_candidate = re.sub(r'<[^>]+>', '', content_after_title.group(1)).strip()
            if desc_candidate and len(desc_candidate) > 20:
                hero_content["description"] = desc_candidate[:300]  # Limit length
    
    # Clean up extracted content
    for key in hero_content:
        if hero_content[key]:
            # Clean HTML entities
            hero_content[key] = (hero_content[key]
                                .replace('&amp;', '&')
                                .replace('&lt;', '<')
                                .replace('&gt;', '>')
                                .replace('&nbsp;', ' ')
                                .strip())
    
    return hero_content

def _generate_smart_preview(html: str) -> str:
    """Generate intelligent preview text that maximizes email opens."""
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    
    # Extract hero content using enhanced extraction
    hero = _extract_hero_content(html)
    
    # Strategy 1: Use hero description if available and compelling
    if hero["description"] and len(hero["description"]) > 30:
        preview_base = hero["description"]
        # Add context for engagement
        if hero["source"]:
            preview = f"{preview_base} • Source: {hero['source']} • Live at {current_time}"
        else:
            preview = f"{preview_base} • Intelligence update at {current_time}"
        
        return preview[:150] + "..." if len(preview) > 150 else preview
    
    # Strategy 2: Use hero title with context
    if hero["title"] and len(hero["title"]) > 15:
        context_suffixes = [
            f"• Breaking analysis & portfolio insights at {current_time}",
            f"• Market intelligence & strategic signals • Live {current_time}",
            f"• Real-time data, news synthesis & investment opportunities",
            f"• Performance metrics, sentiment analysis & key developments"
        ]
        
        suffix_index = now.timetuple().tm_yday % len(context_suffixes)
        preview = f"{hero['title']} {context_suffixes[suffix_index]}"
        
        return preview[:150] + "..." if len(preview) > 150 else preview
    
    # Strategy 3: Scan for meaningful content in cards
    card_content = []
    
    # Look for company performance information
    perf_patterns = [
        r'(\w+)\s*\([A-Z]{2,5}\)[^<]*?(\+?\-?\d+\.\d+%)',
        r'<span[^>]*>([^<]+)</span>[^<]*?(\+?\-?\d+\.\d+%)',
    ]
    
    for pattern in perf_patterns:
        matches = re.finditer(pattern, html, re.I)
        for match in matches:
            company = match.group(1).strip()
            perf = match.group(2)
            if company and not company.isdigit() and len(company) > 2:
                card_content.append(f"{company} {perf}")
                if len(card_content) >= 3:
                    break
    
    if card_content:
        preview = f"Portfolio pulse: {', '.join(card_content[:3])} • Full analysis & news at {current_time}"
        return preview[:150] + "..." if len(preview) > 150 else preview
    
    # Strategy 4: Market sentiment analysis
    up_matches = len(re.findall(r'▲[^<]*?\+\d+\.\d+%', html))
    down_matches = len(re.findall(r'▼[^<]*?\-\d+\.\d+%', html))
    total_positions = up_matches + down_matches
    
    if total_positions > 0:
        up_pct = (up_matches / total_positions) * 100
        if up_pct >= 70:
            sentiment = "Strong gains"
        elif up_pct >= 60:
            sentiment = "Positive session"
        elif up_pct >= 40:
            sentiment = "Mixed performance"
        else:
            sentiment = "Market pressure"
        
        preview = f"{sentiment} across portfolio • {up_matches} up, {down_matches} down • Intelligence & analysis {current_time}"
        return preview[:150] + "..." if len(preview) > 150 else preview
    
    # Strategy 5: Fallback to engaging default
    fallback_options = [
        f"🔥 Live market intelligence • Performance tracking, news analysis & strategic insights • {current_time}",
        f"⚡ Portfolio digest • Real-time data, breaking news & investment signals across your holdings",
        f"💡 Strategic briefing • Market movements, sentiment analysis & opportunities • Updated {current_time}",
        f"📊 Intelligence summary • Live performance metrics, news synthesis & key developments",
    ]
    
    fallback_index = now.timetuple().tm_yday % len(fallback_options)
    return fallback_options[fallback_index]

def _generate_message_id(sender_email: str) -> str:
    """Generate unique, properly formatted Message-ID."""
    timestamp = datetime.now().isoformat()
    unique_str = f"{timestamp}-{os.getpid()}-{socket.gethostname()}"
    hash_part = hashlib.md5(unique_str.encode()).hexdigest()[:12]
    
    if "@" in sender_email:
        domain = sender_email.split("@")[1]
    else:
        domain = "localhost"
    
    return f"<{hash_part}-{int(datetime.now().timestamp())}@{domain}>"

def validate_env():
    """Enhanced environment validation with better error messages."""
    sender = os.getenv("SENDER_EMAIL")
    sender_name = os.getenv("SENDER_NAME", "").strip()
    reply_to = os.getenv("REPLY_TO", "").strip()
    pwd = os.getenv("SENDER_PASSWORD")
    recipients = _split_recipients(os.getenv("RECIPIENT_EMAILS", ""))
    admin_emails = _split_recipients(os.getenv("ADMIN_EMAILS", ""))
    copy_sender = os.getenv("COPY_SENDER", "false").lower() == "true"
    smtp_debug = os.getenv("SMTP_DEBUG", "false").lower() == "true"

    missing = []
    if not sender:
        missing.append("SENDER_EMAIL")
    elif "@" not in sender:
        missing.append("SENDER_EMAIL (invalid format)")
    
    if not pwd:
        missing.append("SENDER_PASSWORD")
    elif len(pwd) < 8:
        missing.append("SENDER_PASSWORD (too short)")
    
    if not recipients:
        missing.append("RECIPIENT_EMAILS")
    else:
        # Validate email formats
        invalid_recipients = [r for r in recipients if "@" not in r or "." not in r.split("@")[1]]
        if invalid_recipients:
            missing.append(f"RECIPIENT_EMAILS (invalid: {', '.join(invalid_recipients)})")

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
    """Enhanced email sending with better deliverability and error handling."""
    cfg = validate_env()
    missing = cfg["missing"]
    if missing:
        error_msg = f"Email configuration errors: {', '.join(missing)}"
        if logger:
            logger.error(error_msg)
        raise RuntimeError(error_msg)

    dry_run = os.getenv("DRY_RUN", "").lower() == "true"

    # Enhanced subject line generation
    if subject is None:
        subject = _generate_enhanced_subject()
    subject = _clean_subject(subject)

    # Enhanced sender display name - CHANGED TO INVESTMENT EDGE
    sender_display_name = cfg["sender_name"] or "Investment Edge"
    sender_disp = formataddr((sender_display_name, cfg["sender"]))

    # Enhanced logging with better information
    masked_to = [_mask_email(r) for r in cfg["recipients"]]
    masked_admins = [_mask_email(a) for a in cfg["admin_emails"]]
    
    if logger:
        logger.info(f"Email config - Recipients: {len(cfg['recipients'])}, "
                   f"Admins: {len(cfg['admin_emails'])}, "
                   f"Copy sender: {cfg['copy_sender']}, "
                   f"Dry run: {dry_run}")

    # Enhanced MIME message construction
    msg = MIMEMultipart("alternative")
    msg["From"] = sender_disp
    msg["To"] = ", ".join(cfg["recipients"][:3])  # Limit visible recipients
    if len(cfg["recipients"]) > 3:
        msg["To"] += f", ... ({len(cfg['recipients']) - 3} more)"
    
    # Enhanced subject with better encoding
    try:
        msg["Subject"] = str(Header(subject, "utf-8"))
    except UnicodeEncodeError:
        # Fallback with ASCII-safe subject
        safe_subject = re.sub(r'[^\x00-\x7F]+', ' ', subject).strip()
        safe_subject = safe_subject or "Intelligence Digest"
        msg["Subject"] = str(Header(safe_subject, "utf-8"))

    if cfg["reply_to"]:
        msg["Reply-To"] = cfg["reply_to"]

    # Enhanced email headers for better deliverability
    msg["Message-ID"] = _generate_message_id(cfg["sender"])
    msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z") or datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
    msg["X-Mailer"] = "Intelligence Digest Engine v3.0"
    msg["X-Priority"] = "3"
    msg["Importance"] = "Normal"
    
    # Anti-spam headers
    msg["List-Unsubscribe"] = "<mailto:unsubscribe@example.com>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg["X-Auto-Response-Suppress"] = "OOF, DR, RN, NRN, AutoReply"
    
    # Content classification
    msg["X-Content-Type"] = "Investment Intelligence"
    msg["X-Content-Category"] = "Financial Newsletter"

    # GitHub Actions metadata (if available)
    github_metadata = {
        "X-GitHub-Run-ID": os.getenv("GITHUB_RUN_ID", ""),
        "X-GitHub-Run-Number": os.getenv("GITHUB_RUN_NUMBER", ""),
        "X-GitHub-SHA": os.getenv("GITHUB_SHA", "")[:12],
        "X-GitHub-Repository": os.getenv("GITHUB_REPOSITORY", ""),
    }
    
    for header, value in github_metadata.items():
        if value:
            msg[header] = value

    # Enhanced preview text extraction and injection
    preview_text = _generate_smart_preview(html)
    
    if logger:
        preview_sample = preview_text[:80] + "..." if len(preview_text) > 80 else preview_text
        logger.info(f"Generated preview: '{preview_sample}'")

    # Enhanced plain text version
    text_alt = re.sub(r'<[^>]+>', ' ', html or "")
    text_alt = re.sub(r'\s+', ' ', text_alt).strip()
    
    if not text_alt or len(text_alt) < 100:
        # Create meaningful plain text fallback
        text_alt = f"""
INTELLIGENCE DIGEST

{preview_text}

This email contains your personalized Intelligence Digest with:
• Real-time portfolio performance metrics
• Breaking news and market analysis  
• Strategic insights and investment signals
• 52-week range tracking and momentum indicators

For the full interactive experience with charts and enhanced formatting, 
please view this email in an HTML-capable client.

---
Intelligence Digest • Engineered with Precision
        """.strip()

    # Enhanced HTML preprocessing
    if html:
        # Inject preview text if not already present
        if "display:none" not in html and preview_text:
            preview_div = f'''
            <div style="display:none;font-size:1px;color:#0b0c10;line-height:1px;
                       max-height:0px;max-width:0px;opacity:0;overflow:hidden;
                       mso-hide:all;" aria-hidden="true">
                {preview_text}
            </div>'''
            
            # Insert after <body> tag
            html = html.replace("<body", preview_div + "<body", 1)
    
    # Attach content with proper encoding
    msg.attach(MIMEText(text_alt, "plain", "utf-8"))
    msg.attach(MIMEText(html or "", "html", "utf-8"))

    # Dry run handling
    if dry_run:
        if logger:
            logger.info(f"[DRY_RUN] Email ready to send:")
            logger.info(f"  Subject: '{subject}'")
            logger.info(f"  Preview: '{preview_text[:100]}...'")
            logger.info(f"  Recipients: {masked_to}")
            logger.info(f"  Admins: {masked_admins}")
            logger.info(f"  HTML size: {len(html)} chars")
            logger.info(f"  Text size: {len(text_alt)} chars")
        return

    # Enhanced recipient list building
    to_addrs = list(dict.fromkeys(cfg["recipients"]))  # Dedupe while preserving order
    
    if cfg["copy_sender"] and cfg["sender"] not in to_addrs:
        to_addrs.append(cfg["sender"])
    
    for admin in cfg["admin_emails"]:
        if admin not in to_addrs:
            to_addrs.append(admin)

    # Enhanced SMTP sending with better error handling
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            if cfg["smtp_debug"]:
                server.set_debuglevel(1)
            
            # Enhanced connection setup
            server.ehlo()
            server.starttls()
            server.ehlo()  # EHLO again after STARTTLS
            
            # Authentication with better error handling
            try:
                server.login(cfg["sender"], cfg["pwd"])
            except smtplib.SMTPAuthenticationError as e:
                raise RuntimeError(f"SMTP authentication failed: {e}") from e
            except smtplib.SMTPException as e:
                raise RuntimeError(f"SMTP login error: {e}") from e
            
            # Send message with delivery tracking
            refused = server.sendmail(cfg["sender"], to_addrs, msg.as_string())
            
            # Enhanced logging
            if logger:
                masked_env = [_mask_email(x) for x in to_addrs]
                logger.info(f"Email sent successfully:")
                logger.info(f"  Subject: '{subject}'")
                logger.info(f"  Recipients: {len(to_addrs)} addresses")
                logger.info(f"  Preview: '{preview_text[:60]}...'")
                
                if refused:
                    logger.warning(f"Some recipients were refused: {refused}")
                else:
                    logger.info("All recipients accepted by server")
            
            # Handle partial failures
            if refused:
                refused_addrs = list(refused.keys())
                raise RuntimeError(f"SMTP refused {len(refused_addrs)} recipients: {refused_addrs}")
                
    except smtplib.SMTPRecipientsRefused as e:
        raise RuntimeError(f"All recipients were refused: {e}") from e
    except smtplib.SMTPServerDisconnected as e:
        raise RuntimeError(f"SMTP server disconnected: {e}") from e
    except smtplib.SMTPException as e:
        raise RuntimeError(f"SMTP error: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected email error: {e}") from e
