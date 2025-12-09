"""
Household Electricity Management - Simplified
Only email notifications for trip count > 5
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_threshold_increase_email(consumer_email: str, consumer_name: str, trip_count: int):
    """
    Send email to consumer when trip count exceeds 5.
    Recommends increasing the threshold power to avoid frequent trips.
    """
    try:
        # Email configuration
        sender_email = "server.supprt.nitdgp@gmail.com"
        sender_password = "rlex vrks ngvo yipt"  # Use app-specific password for Gmail
        
        # Create message
        subject = f"Action Required: Increase Your Power Threshold - {trip_count} Trips Detected"
        
        body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                    <h2 style="color: #d32f2f;">⚠️ High Trip Count Alert</h2>
                    
                    <p>Dear Customer at <strong>{consumer_name}</strong>,</p>
                    
                    <p style="font-size: 16px; line-height: 1.6;">
                        Your electrical circuit has exceeded the safe trip threshold. 
                        Your meter has recorded <strong style="color: #d32f2f; font-size: 18px;">{trip_count} trips</strong> in recent readings.
                    </p>
                    
                    <p style="font-size: 16px; line-height: 1.6;">
                        <strong>⚡ Recommended Action:</strong><br>
                        Please increase your power threshold to prevent frequent circuit trips.
                    </p>
                    
                    <p style="background-color: #e3f2fd; padding: 15px; border-left: 4px solid #2196F3; margin: 20px 0;">
                        <strong>Next Steps:</strong><br>
                        1. Contact the KSEB support team<br>
                        2. Inform them about the frequent trips<br>
                        3. Increase the maximum power limit<br>
                    </p>
                    
                    <p style="font-size: 14px; color: #666;">
                        If the problem persists, please contact support at <strong>support@kseb.com</strong>.
                    </p>
                    
                    <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">
                    
                    <p style="font-size: 12px; color: #999;">
                        This is an automated message from KSEB Smart Grid System.
                    </p>
                </div>
            </body>
        </html>
        """
        
        # Create message object
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = sender_email
        message["To"] = consumer_email
        
        # Attach HTML body
        html_part = MIMEText(body, "html")
        message.attach(html_part)
        
        # Send email via Gmail SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, consumer_email, message.as_string())
        
        print(f"✅ Email sent successfully to {consumer_email}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email to {consumer_email}: {str(e)}")
        return False
