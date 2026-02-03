# backend/notification_service.py
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

class NotificationService:
    """Send notifications to users"""
    
    def notify_loan_funded(self, borrower_email, borrower_name, amount, lender_name):
        subject = "Loan Funded Successfully"
        html_content = f"""
        <html><body>
            <h2>Loan Funded</h2>
            <p>Hi {borrower_name},</p>
            <p>Your loan request has been funded with <strong>${amount:,.2f}</strong> by {lender_name}.</p>
        </body></html>
        """
        return self.send_email(borrower_email, subject, html_content)
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.sender_email = os.getenv('SENDER_EMAIL', 'noreply@blockloan.com')
        self.sender_password = os.getenv('SENDER_PASSWORD', '')

    def send_email(self, recipient, subject, html_content):
        try:
            if not self.sender_password:
                print(f"Email service not configured. Would send: {subject} to {recipient}")
                return True
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = recipient
            part = MIMEText(html_content, "html")
            message.attach(part)
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, recipient, message.as_string())
            print(f"Email sent to {recipient}")
            return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False

    def notify_loan_requested(self, borrower_email, borrower_name, loan_amount):
        subject = "Loan Request Submitted"
        html_content = f"""
        <html><body>
            <h2>Loan Request Submitted</h2>
            <p>Hi {borrower_name},</p>
            <p>Your loan request for <strong>${loan_amount:,.2f}</strong> has been submitted successfully.</p>
        </body></html>
        """
        return self.send_email(borrower_email, subject, html_content)

# Global instance
notification_service = NotificationService()
