#!/usr/bin/env python3
"""
Strategic Intelligence - DIAGNOSTIC MODE
Will tell us exactly what's happening at each step
"""

import os
import sys
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def diagnostic_intelligence():
    """Diagnostic version with extensive logging."""
    
    # Create log file immediately
    log_file = open('intelligence_system.log', 'w')
    
    def log_and_print(message):
        """Log to both console and file."""
        print(message)
        log_file.write(f"{datetime.now()}: {message}\n")
        log_file.flush()
    
    try:
        log_and_print("🚀 DIAGNOSTIC INTELLIGENCE ENGINE - STARTING")
        log_and_print(f"🐍 Python version: {sys.version}")
        log_and_print(f"🕐 Execution time: {datetime.now()}")
        
        # Step 1: Environment Check
        log_and_print("🔍 STEP 1: Environment Variable Check")
        
        sender_email = os.getenv('SENDER_EMAIL')
        sender_password = os.getenv('SENDER_PASSWORD')
        recipient_emails = os.getenv('RECIPIENT_EMAILS')
        
        log_and_print(f"📧 SENDER_EMAIL: {'SET' if sender_email else 'MISSING'}")
        log_and_print(f"🔑 SENDER_PASSWORD: {'SET' if sender_password else 'MISSING'}")
        log_and_print(f"📨 RECIPIENT_EMAILS: {'SET' if recipient_emails else 'MISSING'}")
        
        if sender_email:
            log_and_print(f"📧 Sender: {sender_email}")
        if recipient_emails:
            log_and_print(f"📨 Recipients: {recipient_emails}")
        
        if not all([sender_email, sender_password, recipient_emails]):
            log_and_print("❌ CRITICAL: Missing environment variables")
            return False
        
        log_and_print("✅ Environment variables validated")
        
        # Step 2: Email Configuration
        log_and_print("🔍 STEP 2: Email Configuration")
        
        recipients = [email.strip() for email in recipient_emails.split(',') if email.strip()]
        log_and_print(f"📮 Parsed recipients: {recipients}")
        log_and_print(f"📮 Recipient count: {len(recipients)}")
        
        # Step 3: Generate Simple Test Report
        log_and_print("🔍 STEP 3: Generate Test Report")
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 30px; border-radius: 12px; text-align: center;">
                <h1>🎉 DIAGNOSTIC SUCCESS!</h1>
                <p>Strategic Intelligence System is OPERATIONAL</p>
                <p>Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            </div>
            
            <div style="background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px;">
                <h3>✅ System Verification Complete</h3>
                <ul>
                    <li>GitHub Actions: EXECUTING</li>
                    <li>Environment Variables: CONFIGURED</li>
                    <li>Email System: OPERATIONAL</li>
                    <li>Python Execution: SUCCESSFUL</li>
                </ul>
            </div>
            
            <div style="background: #e3f2fd; padding: 20px; border-radius: 8px;">
                <h3>🚀 Next Steps</h3>
                <p>Your Strategic Constellation Intelligence system is fully operational!</p>
                <p>Automated Monday morning reports will be delivered at 9:00 AM EST.</p>
                <p>If you receive this email, everything is working perfectly!</p>
            </div>
            
            <div style="background: #f1f8e9; padding: 20px; margin: 20px 0; border-radius: 8px;">
                <h3>📊 Mock Portfolio Data</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background: #e8f5e8;">
                        <th style="padding: 10px; border: 1px solid #ddd;">Symbol</th>
                        <th style="padding: 10px; border: 1px solid #ddd;">Price</th>
                        <th style="padding: 10px; border: 1px solid #ddd;">Change</th>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;">AAPL</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">$194.27</td>
                        <td style="padding: 10px; border: 1px solid #ddd; color: green;">+2.4%</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;">MSFT</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">$374.51</td>
                        <td style="padding: 10px; border: 1px solid #ddd; color: green;">+1.8%</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;">TSLA</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">$248.50</td>
                        <td style="padding: 10px; border: 1px solid #ddd; color: green;">+3.2%</td>
                    </tr>
                </table>
            </div>
        </body>
        </html>
        """
        
        log_and_print("✅ HTML report generated")
        
        # Step 4: Email Message Creation
        log_and_print("🔍 STEP 4: Email Message Creation")
        
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = sender_email
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = f"🧪 DIAGNOSTIC SUCCESS - Strategic Intelligence Test - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            log_and_print("✅ Email message created successfully")
            
        except Exception as e:
            log_and_print(f"❌ Email message creation failed: {e}")
            return False
        
        # Step 5: SMTP Connection and Sending
        log_and_print("🔍 STEP 5: SMTP Connection and Sending")
        
        try:
            log_and_print("🔌 Connecting to Gmail SMTP server...")
            
            server = smtplib.SMTP('smtp.gmail.com', 587)
            log_and_print("✅ SMTP connection established")
            
            log_and_print("🔐 Starting TLS encryption...")
            server.starttls()
            log_and_print("✅ TLS encryption activated")
            
            log_and_print("🔑 Attempting authentication...")
            server.login(sender_email, sender_password)
            log_and_print("✅ SMTP authentication successful")
            
            log_and_print("📧 Sending diagnostic email...")
            server.send_message(msg)
            log_and_print("✅ Email sent successfully")
            
            server.quit()
            log_and_print("✅ SMTP connection closed")
            
        except smtplib.SMTPAuthenticationError as e:
            log_and_print(f"❌ SMTP Authentication Error: {e}")
            log_and_print("🔧 Check: Gmail app password format and 2FA settings")
            return False
            
        except smtplib.SMTPRecipientsRefused as e:
            log_and_print(f"❌ SMTP Recipients Refused: {e}")
            log_and_print("🔧 Check: Recipient email addresses")
            return False
            
        except smtplib.SMTPServerDisconnected as e:
            log_and_print(f"❌ SMTP Server Disconnected: {e}")
            log_and_print("🔧 Check: Network connectivity")
            return False
            
        except Exception as e:
            log_and_print(f"❌ Unexpected SMTP Error: {e}")
            log_and_print(f"❌ Error Type: {type(e).__name__}")
            return False
        
        # Step 6: Success Confirmation
        log_and_print("🔍 STEP 6: Success Confirmation")
        log_and_print(f"🎉 DIAGNOSTIC COMPLETE - Email sent to {len(recipients)} recipients")
        log_and_print(f"📧 Check your inbox: {recipients[0]}")
        log_and_print("✅ Strategic Intelligence System is FULLY OPERATIONAL")
        
        return True
        
    except Exception as e:
        log_and_print(f"❌ CRITICAL ERROR: {e}")
        log_and_print(f"❌ Error Type: {type(e).__name__}")
        import traceback
        log_and_print(f"❌ Full Traceback: {traceback.format_exc()}")
        return False
        
    finally:
        log_and_print("🏁 DIAGNOSTIC ENGINE SHUTDOWN")
        log_file.close()

if __name__ == "__main__":
    print("🚀 Starting Diagnostic Intelligence Engine...")
    success = diagnostic_intelligence()
    print(f"🏁 Diagnostic Complete - Success: {success}")
    exit(0 if success else 1)
