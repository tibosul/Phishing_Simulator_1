import smtplib
import logging
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from flask import current_app, render_template_string
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
    
    MODIFICAT: Folosește template-urile din /templates/emails/ în loc de baza de date
    """
    
    def __init__(self):
        self.smtp_server = None
        self.logger = logging.getLogger(__name__)
        
        # Mapare template-uri disponibile
        self.available_templates = {
            'security': 'emails/revolut_security.html',
            'promotion': 'emails/revolut_promotion.html', 
            'update': 'emails/revolut_update.html'
        }
    
    def _get_smtp_connection(self):
        """
        Creează conexiunea SMTP folosind configurația din Flask
        """
        try:
            server = current_app.config.get('MAIL_SERVER')
            port = current_app.config.get('MAIL_PORT', 587)
            username = current_app.config.get('MAIL_USERNAME')
            password = current_app.config.get('MAIL_PASSWORD')
            use_tls = current_app.config.get('MAIL_USE_TLS', True)
            
            if not server or not username or not password:
                raise ValueError("Email configuration incomplete. Check MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD")
            
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
    
    def get_template_path(self, template_name):
        """
        Returnează calea către template-ul de email
        
        Args:
            template_name: Numele template-ului (security, promotion, update)
            
        Returns:
            str: Calea către fișierul template
        """
        if template_name in self.available_templates:
            return self.available_templates[template_name]
        
        # Default la security dacă nu găsește
        return self.available_templates['security']
    
    def load_template_content(self, template_path):
        """
        Încarcă conținutul template-ului din fișier
        
        Args:
            template_path: Calea către template (ex: emails/revolut_security.html)
            
        Returns:
            str: Conținutul template-ului
        """
        try:
            # Construiește calea completă către template
            template_dir = os.path.join(current_app.root_path, 'templates')
            full_path = os.path.join(template_dir, template_path)
            
            if not os.path.exists(full_path):
                raise FileNotFoundError(f"Template not found: {full_path}")
            
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.logger.debug(f"Template loaded: {template_path}")
            return content
            
        except Exception as e:
            self.logger.error(f"Error loading template {template_path}: {str(e)}")
            # Fallback la un template minimal
            return self._get_fallback_template()
    
    def _get_fallback_template(self):
        """
        Template minimal de fallback dacă nu găsește fișierul
        """
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Revolut Security Alert</title>
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #0075eb;">Security Alert</h2>
            <p>Dear {{target_name}},</p>
            <p>We detected suspicious activity on your Revolut account.</p>
            <p><a href="{{tracking_link}}" style="background: #0075eb; color: white; padding: 10px 20px; text-decoration: none;">Verify Account</a></p>
            <p><small>This is an automated message from Revolut Security.</small></p>
            <img src="{{tracking_pixel}}" width="1" height="1" alt="" />
        </body>
        </html>
        '''
    
    def render_email_template(self, template_name, target, campaign):
        """
        Renderizează template-ul email cu datele target-ului și campaniei
        
        Args:
            template_name: Numele template-ului (security, promotion, update)
            target: Target-ul destinatar
            campaign: Campania asociată
            
        Returns:
            tuple: (subject_rendered, content_rendered)
        """
        try:
            # Încarcă template-ul din fișier
            template_path = self.get_template_path(template_name)
            template_content = self.load_template_content(template_path)
            
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
            
            # Renderizează template-ul cu Jinja2
            template = Template(template_content)
            rendered_content = template.render(**template_data)
            
            # Extrage subiectul din template (dacă există în <title> sau folosește default)
            subject = self._extract_subject_from_template(rendered_content, template_name)
            
            # Renderizează subiectul cu datele template-ului
            subject_template = Template(subject)
            rendered_subject = subject_template.render(**template_data)
            
            self.logger.debug(f"Template {template_name} rendered for target {target.email}")
            return rendered_subject, rendered_content
            
        except Exception as e:
            self.logger.error(f"Error rendering template: {str(e)}")
            raise
    
    def _extract_subject_from_template(self, content, template_name):
        """
        Extrage subiectul din template (din <title> tag) sau folosește default
        """
        import re
        
        # Încearcă să găsească <title> tag
        title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
        if title_match:
            return title_match.group(1).strip()
        
        # Default subjects pentru fiecare template
        default_subjects = {
            'security': 'Security Alert: Immediate Action Required',
            'promotion': 'Exclusive Offer: {{target_first_name}}, Don\'t Miss Out!',
            'update': 'Important: Account Update Required'
        }
        
        return default_subjects.get(template_name, 'Important Message from Revolut')
    
    def send_phishing_email(self, campaign_id, target_id, template_name='security'):
        """
        Trimite un email de phishing către o țintă specifică
        
        Args:
            campaign_id: ID-ul campaniei
            target_id: ID-ul țintei
            template_name: Numele template-ului (security, promotion, update)
            
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
            
            # Validează email-ul țintei
            validate_email(target.email)
            
            # Verifică dacă template-ul există
            if template_name not in self.available_templates:
                self.logger.warning(f"Template {template_name} not found, using security template")
                template_name = 'security'
            
            # Renderizează template-ul
            subject, content = self.render_email_template(template_name, target, campaign)
            
            # Creează mesajul email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = current_app.config.get('MAIL_DEFAULT_SENDER')
            msg['To'] = target.email
            
            # Adaugă headers pentru tracking
            msg['Message-ID'] = f"<{campaign.id}.{target.id}.{datetime.now().timestamp()}@phishing-sim>"
            msg['X-Campaign-ID'] = str(campaign.id)
            msg['X-Target-ID'] = str(target.id)
            
            # Convertește conținutul în HTML
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
                    'template_name': template_name,
                    'subject': subject,
                    'email_length': len(content)
                }
            )
            
            self.logger.info(f"Phishing email sent: {target.email} (Template: {template_name})")
            log_security_event('email_sent', f"Phishing email sent to {target.email}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send phishing email: {str(e)}")
            raise
    
    def send_campaign_emails(self, campaign_id, template_name='security', batch_size=10, delay_seconds=5):
        """
        Trimite email-uri pentru întreaga campanie în batch-uri
        
        Args:
            campaign_id: ID-ul campaniei
            template_name: Numele template-ului de folosit
            batch_size: Numărul de email-uri per batch
            delay_seconds: Delay între batch-uri
            
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
                        self.send_phishing_email(campaign_id, target.id, template_name)
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
    
    def list_available_templates(self):
        """
        Returnează lista template-urilor disponibile
        
        Returns:
            dict: Template-urile disponibile cu descrieri
        """
        return {
            'security': {
                'name': 'Security Alert',
                'description': 'Urgent security alert requiring immediate action',
                'file': self.available_templates['security']
            },
            'promotion': {
                'name': 'Promotional Offer', 
                'description': 'Special promotion or offer email',
                'file': self.available_templates['promotion']
            },
            'update': {
                'name': 'Account Update',
                'description': 'Account information update requirement',
                'file': self.available_templates['update']
            }
        }
    
    def send_test_email(self, template_name, test_email):
        """
        Trimite un email de test pentru verificarea template-ului
        
        Args:
            template_name: Numele template-ului
            test_email: Email-ul de test
            
        Returns:
            bool: True dacă email-ul de test a fost trimis
        """
        try:
            validate_email(test_email)
            
            # Creează target fictiv pentru test
            test_target = Target(
                campaign_id=0,
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
            subject, content = self.render_email_template(template_name, test_target, test_campaign)
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[TEST] {subject}"
            msg['From'] = current_app.config.get('MAIL_DEFAULT_SENDER')
            msg['To'] = test_email
            
            html_part = MIMEText(content, 'html', 'utf-8')
            msg.attach(html_part)
            
            smtp = self._get_smtp_connection()
            smtp.send_message(msg)
            smtp.quit()
            
            self.logger.info(f"Test email sent to {test_email} using template {template_name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send test email: {str(e)}")
            raise