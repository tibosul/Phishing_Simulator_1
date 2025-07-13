"""
Email Service for Phishing Simulator

Handles email sending functionality using Flask-Mail
"""

from flask import current_app
from flask_mail import Mail, Message
import logging

# Initialize Mail instance
mail = Mail()

def init_mail(app):
    """Initialize Flask-Mail with the app"""
    mail.init_app(app)

def send_email(to, subject, body, html_body=None):
    """
    Send an email
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Plain text body
        html_body: HTML body (optional)
        
    Returns:
        bool: True if email was sent successfully
    """
    try:
        msg = Message(
            subject=subject,
            recipients=[to] if isinstance(to, str) else to,
            body=body,
            html=html_body,
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        
        mail.send(msg)
        current_app.logger.info(f"Email sent successfully to {to}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Failed to send email to {to}: {str(e)}")
        return False

class EmailService:
    """Service class for email operations"""
    
    @staticmethod
    def send_phishing_email(target, campaign, template):
        """
        Send a phishing email to a target
        
        Args:
            target: Target model instance
            campaign: Campaign model instance  
            template: Template model instance
            
        Returns:
            bool: True if email was sent successfully
        """
        # This would be implemented based on the actual models
        # For now, just a placeholder
        return send_email(
            to=target.email if hasattr(target, 'email') else 'test@example.com',
            subject="Phishing Test Email",
            body="This is a phishing simulation email.",
            html_body="<p>This is a phishing simulation email.</p>"
        )
    
    @staticmethod 
    def send_notification_email(to, subject, message):
        """Send a notification email"""
        return send_email(to, subject, message)
