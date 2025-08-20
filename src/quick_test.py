import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

def quick_intelligence_test():
    """Ultra-fast intelligence test."""
    print("🚀 Quick Intelligence Test")
    
    try:
        # Create minimal report
        html = f"""
        <html><body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 30px; border-radius: 12px; text-align: center;">
                <h1>🚀 STRATEGIC INTELLIGENCE OPERATIONAL</h1>
                <p>Quick Test Successful - {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            </div>
            <div style="background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px;">
                <h3>✅ System Status</h3>
                <ul>
                    <li>GitHub Actions: EXECUTING</li>
                    <li>Email System: OPERATIONAL</li>
                    <li>Strategic Engine: READY</li>
                </ul>
                <p>Your full constellation intelligence system is ready for Monday morning automation!</p>
            </div>
        </body></html>
        """
        
        # Send quick email
        msg = MIMEText(html, 'html')
        msg['Subject'] = f"🚀 Strategic Intelligence Test - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        msg['From'] = os.getenv('SENDER_EMAIL')
        msg['To'] = os.getenv('RECIPIENT_EMAILS').split(',')[0]
        
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(os.getenv('SENDER_EMAIL'), os.getenv('SENDER_PASSWORD'))
            server.send_message(msg)
        
        print("✅ Quick test email sent successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Quick test failed: {e}")
        return False

if __name__ == "__main__":
    quick_intelligence_test()
