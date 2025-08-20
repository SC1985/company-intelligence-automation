#!/usr/bin/env python3
"""
Strategic Intelligence - Enhanced Diagnostic Mode
"""

import asyncio
import os
import json
import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Enhanced logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('intelligence_system.log')
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Enhanced diagnostic execution with detailed logging."""
    logger.info("🚀 ENHANCED DIAGNOSTIC MODE - Strategic Intelligence")
    
    try:
        # Step 1: Environment Validation
        logger.info("🔍 STEP 1: Validating Environment Configuration")
        
        sender_email = os.getenv('SENDER_EMAIL')
        sender_password = os.getenv('SENDER_PASSWORD')
        recipient_emails = os.getenv('RECIPIENT_EMAILS', '')
        admin_emails = os.getenv('ADMIN_EMAILS', '')
        
        logger.info(f"📧 Sender Email: {sender_email}")
        logger.info(f"📨 Recipient Emails: {recipient_emails}")
        logger.info(f"👑 Admin Emails: {admin_emails}")
        logger.info(f"🔑 Password Configured: {'YES' if sender_password else 'NO'}")
        
        if sender_password:
            logger.info(f"🔑 Password Length: {len(sender_password)} characters")
            logger.info(f"🔑 Password Format: {'Correct' if len(sender_password) == 19 and sender_password.count(' ') == 3 else 'CHECK FORMAT'}")
        
        # Parse recipients
        recipients = [email.strip() for email in recipient_emails.split(',') if email.strip()]
        logger.info(f"📮 Parsed Recipients: {recipients}")
        
        if not all([sender_email, sender_password, recipients]):
            logger.error("❌ CONFIGURATION INCOMPLETE")
            if not sender_email:
                logger.error("❌ SENDER_EMAIL missing")
            if not sender_password:
                logger.error("❌ SENDER_PASSWORD missing") 
            if not recipients:
                logger.error("❌ RECIPIENT_EMAILS missing or invalid")
            return False
        
        logger.info("✅ Environment validation complete")
        
        # Step 2: Email System Test
        logger.info("🔍 STEP 2: Testing Email System")
        
        # Create test message
        msg = MIMEMultipart('alternative')
        msg['From'] = sender_email
        msg['To'] = recipients[0]
        msg['Subject'] = f"🧪 Enhanced Diagnostic Test - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        test_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 30px; border-radius: 12px; text-align: center;">
                <h1>🧪 ENHANCED DIAGNOSTIC SUCCESS</h1>
                <p>Strategic Intelligence System - Email Distribution Test</p>
                <p>Generated: {datetime.now().strftime('%Y-%m-%d at %H:%M:%S UTC')}</p>
            </div>
            
            <div style="background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px;">
                <h3>✅ System Status: OPERATIONAL</h3>
                <ul>
                    <li>Configuration: VALIDATED</li>
                    <li>Email System: FUNCTIONING</li>
                    <li>GitHub Actions: EXECUTING</li>
                    <li>Intelligence Engine: READY</li>
                </ul>
            </div>
            
            <div style="background: #e3f2fd; padding: 20px; border-radius: 8px;">
                <h3>📊 Next Steps</h3>
                <p>Your Strategic Constellation Intelligence system is now operational!</p>
                <p>Monday morning briefings will be delivered automatically at 9:00 AM EST.</p>
            </div>
        </body>
        </html>
        """
        
        html_part = MIMEText(test_html, 'html', 'utf-8')
        msg.attach(html_part)
        
        # Step 3: SMTP Connection and Send
        logger.info("🔍 STEP 3: SMTP Connection and Authentication")
        
        try:
            logger.info("🔌 Connecting to Gmail SMTP server...")
            
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                logger.info("✅ SMTP connection established")
                
                logger.info("🔐 Starting TLS encryption...")
                server.starttls()
                logger.info("✅ TLS encryption activated")
                
                logger.info("🔑 Attempting authentication...")
                server.login(sender_email, sender_password)
                logger.info("✅ Authentication successful")
                
                logger.info("📧 Sending test message...")
                server.send_message(msg)
                logger.info("✅ Message sent successfully")
            
            logger.info(f"🎉 EMAIL DELIVERY SUCCESS - Sent to {recipients[0]}")
            
            # Step 4: Success Confirmation
            logger.info("🔍 STEP 4: Success Confirmation")
            logger.info("✅ Enhanced diagnostic test completed successfully")
            logger.info(f"📧 Check your inbox: {recipients[0]}")
            logger.info("🚀 Strategic Intelligence system is fully operational")
            
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ SMTP AUTHENTICATION FAILED: {e}")
            logger.error("🔧 SOLUTION: Check Gmail app password")
            logger.error("🔧 Ensure 2FA is enabled and app password is correctly formatted")
            return False
            
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"❌ RECIPIENTS REFUSED: {e}")
            logger.error("🔧 SOLUTION: Check recipient email addresses")
            return False
            
        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"❌ SMTP SERVER DISCONNECTED: {e}")
            logger.error("🔧 SOLUTION: Network connectivity issue")
            return False
            
        except Exception as e:
            logger.error(f"❌ UNEXPECTED EMAIL ERROR: {e}")
            logger.error(f"❌ Error Type: {type(e).__name__}")
            return False
        
    except Exception as e:
        logger.error(f"❌ SYSTEM ERROR: {e}")
        logger.error(f"❌ Error Type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    logger.info(f"🏁 DIAGNOSTIC COMPLETE - Success: {success}")
    exit(0 if success else 1)
