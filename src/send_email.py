#!/usr/bin/env python3
"""
Investment Edge Email Sender
Sends the generated HTML email via Gmail
"""

import os
import json
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_email():
    """Send the generated email"""
    try:
        # Get credentials from environment
        gmail_address = os.getenv('GMAIL_ADDRESS')
        gmail_password = os.getenv('GMAIL_APP_PASSWORD')
        recipient = os.getenv('RECIPIENT_EMAIL', gmail_address)  # Default to sender
        
        if not gmail_address or not gmail_password:
            logger.error("Gmail credentials not found in environment variables")
            return False
        
        # Load the generated HTML
        with open('email_output.html', 'r') as f:
            html_content = f.read()
        
        # Load digest data for subject line
        with open('daily_digest.json', 'r') as f:
            digest_data = json.load(f)
        
        # Generate subject line
        subject = "Investment Edge: "
        if digest_data.get('top_articles'):
            # Use first article title (truncated)
            article_title = digest_data['top_articles'][0].get('title', 'Daily Market Update')
            # Clean up title
            article_title = article_title.replace('\n', ' ').strip()
            # Truncate if too long
            if len(article_title) > 50:
                article_title = article_title[:47] + '...'
            subject += article_title
        else:
            # Fallback subject
            subject += "Daily Market Update"
        
        # Add date to subject
        subject += f" - {datetime.now().strftime('%B %d')}"
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = gmail_address
        msg['To'] = recipient
        
        # Add plain text version (fallback)
        text_content = """
Investment Edge Daily Digest

Your daily market intelligence report is ready.

This email is best viewed in an HTML-capable email client.

---
Investment Edge
        """
        
        # Attach parts
        part1 = MIMEText(text_content, 'plain')
        part2 = MIMEText(html_content, 'html')
        
        msg.attach(part1)
        msg.attach(part2)
        
        # Send email
        logger.info(f"Connecting to Gmail SMTP server...")
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(gmail_address, gmail_password)
            
            logger.info(f"Sending email to {recipient}...")
            server.send_message(msg)
            
        logger.info(f"Email sent successfully to {recipient}")
        logger.info(f"Subject: {subject}")
        
        # Log some stats
        stats = digest_data.get('stats', {})
        if stats:
            logger.info(f"Digest stats: {stats.get('gainers')} gainers, {stats.get('losers')} losers, {stats.get('alerts')} alerts")
        
        return True
        
    except FileNotFoundError as e:
        logger.error(f"Required file not found: {e}")
        return False
    except smtplib.SMTPAuthenticationError:
        logger.error("Gmail authentication failed. Check your app password.")
        return False
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return False

def main():
    """Main execution"""
    success = send_email()
    return 0 if success else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
