import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from flask import current_app
from jinja2 import Template

from models.campaign import Campaign
from models.target import Target
from models.template import Template as EmailTemplate
from models.tracking import Tracking
from utils.database import db
from utils.helpers import build_tracking_url, build_tracking_pixel_url, get_client_ip, log_security_event
from utils.validators import validate_email, ValidationError


class EmailService:
    """
    Service pentru trimiterea email-urilor de phishing
    
    Features:
    - Trimitere email-uri personalizate
    - Tracking pixel pentru deschideri
    - Link-uri cu tracking pentru click-uri
    - Template rendering cu Jinja2
    - Logging complet pentru audit
    """
    
    def __init__(self):
        self.smtp_server = None
        self.logger = logging.getLogger(__name__)
    
    def _get_smtp_connection(self):
        """
        Creează conexiunea SMTP folosind configurația din Flask
        
        Returns:
            smtplib.SMTP: Conexiunea SMTP configurată
        """
        try:
            server = current_app.config.get('MAIL_SERVER')
            port = current_app.config.get('MAIL_PORT', 587)
            username = current_app.config.get('MAIL_USERNAME')
            password = current_app.config.get('MAIL_PASSWORD')
            use_tls = current_app.config.get('MAIL_USE_TLS', True)
            
            if not server or not username or not password:
                raise ValueError("Email configuration incomplete. Check MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD")
            
            # Conectează la server
            smtp = smtplib.SMTP(server, port)
            smtp.ehlo()
            
            if use_tls:
                smtp.starttls()
                smtp.ehlo()
            
            smtp.login(username, password)
            
            self.logger.info(f"SMTP connection established to {server}:{port}")
            return smtp
            
        except Exception as e:
            self.logger.error(f"Failed to connect to SMTP server: {str(e)}")
            raise
    
    def render_email_template(self, template, target, campaign):
        """
        Renderizează template-ul email cu datele target-ului și campaniei
        
        Args:
            template: Template-ul de email
            target: Target-ul destinatar
            campaign: Campania asociată
            
        Returns:
            tuple: (subject_rendered, content_rendered)
        """
        try:
            # Pregătește datele pentru template
            template_data = {
                # Target data
                'target_name': target.display_name,
                'target_first_name': target.first_name or 'User',
                'target_last_name': target.last_name or '',
                'target_email': target.email,
                'target_company': target.company or 'Your Company',
                'target_position': target.position or 'Employee',
                
                # Campaign data
                'campaign_name': campaign.name,
                'campaign_id': campaign.id,
                
                # URLs și tracking
                'tracking_link': build_tracking_url(campaign.id, target.id, 'login'),
                'tracking_pixel': build_tracking_pixel_url(campaign.id, target.id),
                'unsubscribe_link': f"{current_app.config.get('BASE_URL')}/unsubscribe?c={campaign.id}&t={target.id}",
                
                # Date și timp
                'current_date': datetime.now().strftime('%Y-%m-%d'),
                'current_year': datetime.now().year,
                'current_time': datetime.now().strftime('%H:%M'),
                
                # Personalizare suplimentară
                'sender_name': 'Revolut Security Team',
                'company_name': 'Revolut',
                'support_email': 'security@revolut.com'
            }
            
            # Renderizează subiectul
            subject_template = Template(template.subject or "Security Alert")
            rendered_subject = subject_template.render(**template_data)
            
            # Renderizează conținutul
            content_template = Template(template.content)
            rendered_content = content_template.render(**template_data)
            
            self.logger.debug(f"Template rendered for target {target.email}")
            return rendered_subject, rendered_content
            
        except Exception as e:
            self.logger.error(f"Error rendering template: {str(e)}")
            raise
    
    def send_phishing_email(self, campaign_id, target_id, template_id=None):
        """
        Trimite un email de phishing către o țintă specifică
        
        Args:
            campaign_id: ID-ul campaniei
            target_id: ID-ul țintei
            template_id: ID-ul template-ului (opțional, folosește primul disponibil)
            
        Returns:
            bool: True dacă email-ul a fost trimis cu succes
        """
        try:
            # Încarcă entitățile
            campaign = Campaign.query.get(campaign_id)
            if not campaign:
                raise ValidationError(f"Campaign {campaign_id} not found")
            
            target = Target.query.get(target_id)
            if not target:
                raise ValidationError(f"Target {target_id} not found")
            
            # Găsește template-ul
            if template_id:
                template = EmailTemplate.query.get(template_id)
            else:
                # Folosește primul template de email disponibil
                template = EmailTemplate.query.filter_by(type='email', is_active=True).first()
            
            if not template:
                raise ValidationError("No email template available")
            
            # Validează email-ul țintei
            validate_email(target.email)
            
            # Renderizează template-ul
            subject, content = self.render_email_template(template, target, campaign)
            
            # Creează mesajul email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = current_app.config.get('MAIL_DEFAULT_SENDER')
            msg['To'] = target.email
            
            # Adaugă headers pentru tracking
            msg['Message-ID'] = f"<{campaign.id}.{target.id}.{datetime.now().timestamp()}@phishing-sim>"
            msg['X-Campaign-ID'] = str(campaign.id)
            msg['X-Target-ID'] = str(target.id)
            
            # Convertește conținutul în HTML și text
            html_part = MIMEText(content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Trimite email-ul
            smtp = self._get_smtp_connection()
            smtp.send_message(msg)
            smtp.quit()
            
            # Actualizează statusul țintei
            target.mark_email_sent()
            
            # Creează eveniment de tracking
            Tracking.create_event(
                campaign_id=campaign.id,
                event_type='email_sent',
                target_id=target.id,
                ip_address=get_client_ip(),
                extra_data={
                    'template_id': template.id,
                    'subject': subject,
                    'email_length': len(content)
                }
            )
            
            # Incrementează usage pentru template
            template.increment_usage()
            
            self.logger.info(f"Phishing email sent: {target.email} (Campaign: {campaign.name})")
            log_security_event('email_sent', f"Phishing email sent to {target.email}", get_client_ip())
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send phishing email: {str(e)}")
            raise
    
    def send_campaign_emails(self, campaign_id, batch_size=10, delay_seconds=5):
        """
        Trimite email-uri pentru întreaga campanie în batch-uri
        
        Args:
            campaign_id: ID-ul campaniei
            batch_size: Numărul de email-uri per batch
            delay_seconds: Delay între batch-uri (pentru a evita spam filters)
            
        Returns:
            dict: Statistici despre trimitere
        """
        import time
        
        try:
            campaign = Campaign.query.get(campaign_id)
            if not campaign:
                raise ValidationError(f"Campaign {campaign_id} not found")
            
            if not campaign.is_active:
                raise ValidationError("Campaign must be active to send emails")
            
            # Găsește țintele care nu au primit email încă
            targets = Target.query.filter_by(
                campaign_id=campaign_id,
                email_sent=False
            ).all()
            
            if not targets:
                self.logger.warning(f"No targets to send emails for campaign {campaign_id}")
                return {'sent': 0, 'failed': 0, 'skipped': len(targets)}
            
            stats = {'sent': 0, 'failed': 0, 'skipped': 0}
            
            # Procesează în batch-uri
            for i in range(0, len(targets), batch_size):
                batch = targets[i:i + batch_size]
                
                for target in batch:
                    try:
                        self.send_phishing_email(campaign_id, target.id)
                        stats['sent'] += 1
                        
                    except Exception as e:
                        self.logger.error(f"Failed to send email to {target.email}: {str(e)}")
                        stats['failed'] += 1
                
                # Delay între batch-uri
                if i + batch_size < len(targets):
                    self.logger.info(f"Processed batch {i//batch_size + 1}, waiting {delay_seconds}s...")
                    time.sleep(delay_seconds)
            
            self.logger.info(f"Campaign {campaign.name} email sending complete: {stats}")
            log_security_event('campaign_emails_sent', f"Campaign {campaign.name}: {stats['sent']} emails sent")
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to send campaign emails: {str(e)}")
            raise
    
    def send_test_email(self, template_id, test_email):
        """
        Trimite un email de test pentru verificarea template-ului
        
        Args:
            template_id: ID-ul template-ului
            test_email: Email-ul de test
            
        Returns:
            bool: True dacă email-ul de test a fost trimis
        """
        try:
            template = EmailTemplate.query.get(template_id)
            if not template:
                raise ValidationError(f"Template {template_id} not found")
            
            validate_email(test_email)
            
            # Creează target fictiv pentru test
            test_target = Target(
                campaign_id=0,  # Campaign ID fictiv
                email=test_email,
                first_name="Test",
                last_name="User",
                company="Test Company"
            )
            
            # Creează campanie fictivă pentru test
            test_campaign = Campaign(
                name="Test Campaign",
                type="email",
                description="This is a test"
            )
            test_campaign.id = 0
            
            # Renderizează și trimite
            subject, content = self.render_email_template(template, test_target, test_campaign)
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[TEST] {subject}"
            msg['From'] = current_app.config.get('MAIL_DEFAULT_SENDER')
            msg['To'] = test_email
            
            html_part = MIMEText(content, 'html', 'utf-8')
            msg.attach(html_part)
            
            smtp = self._get_smtp_connection()
            smtp.send_message(msg)
            smtp.quit()
            
            self.logger.info(f"Test email sent to {test_email} using template {template.name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send test email: {str(e)}")
            raise
    
    def get_email_statistics(self, campaign_id=None):
        """
        Returnează statistici despre email-urile trimise
        
        Args:
            campaign_id: ID-ul campaniei (opțional, pentru toate campaniile)
            
        Returns:
            dict: Statistici email
        """
        try:
            from sqlalchemy import func
            
            query = db.session.query(
                func.count(Tracking.id).label('total_sent')
            ).filter(Tracking.event_type == 'email_sent')
            
            if campaign_id:
                query = query.filter(Tracking.campaign_id == campaign_id)
            
            total_sent = query.scalar() or 0
            
            # Calculează rata de deschidere
            opens_query = db.session.query(
                func.count(Tracking.id).label('total_opens')
            ).filter(Tracking.event_type == 'email_opened')
            
            if campaign_id:
                opens_query = opens_query.filter(Tracking.campaign_id == campaign_id)
            
            total_opens = opens_query.scalar() or 0
            
            # Calculează rata de click
            clicks_query = db.session.query(
                func.count(Tracking.id).label('total_clicks')
            ).filter(Tracking.event_type == 'link_clicked')
            
            if campaign_id:
                clicks_query = clicks_query.filter(Tracking.campaign_id == campaign_id)
            
            total_clicks = clicks_query.scalar() or 0
            
            open_rate = (total_opens / total_sent * 100) if total_sent > 0 else 0
            click_rate = (total_clicks / total_sent * 100) if total_sent > 0 else 0
            
            return {
                'total_sent': total_sent,
                'total_opens': total_opens,
                'total_clicks': total_clicks,
                'open_rate': round(open_rate, 2),
                'click_rate': round(click_rate, 2)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting email statistics: {str(e)}")
            return {}
    
    @staticmethod
    def validate_email_config():
        """
        Validează configurația email din Flask config
        
        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            required_configs = ['MAIL_SERVER', 'MAIL_USERNAME', 'MAIL_PASSWORD']
            
            for config_key in required_configs:
                if not current_app.config.get(config_key):
                    return False, f"Missing configuration: {config_key}"
            
            # Test conexiunea
            email_service = EmailService()
            smtp = email_service._get_smtp_connection()
            smtp.quit()
            
            return True, "Email configuration is valid"
            
        except Exception as e:
            return False, f"Email configuration error: {str(e)}"