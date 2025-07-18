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
import threading
import time
from queue import Queue

from models.campaign import Campaign
from models.target import Target
from models.template import Template as EmailTemplate
from models.tracking import Tracking
from utils.database import db
from utils.helpers import build_tracking_url, build_tracking_pixel_url, get_client_ip, log_security_event
from utils.validators import validate_email, ValidationError


class EmailService:
    """
    Service complet pentru trimiterea email-urilor de phishing
    
    Features:
    - Template loading din fișiere și baza de date
    - Batch sending cu rate limiting
    - Email tracking (opens, clicks)
    - Queue management pentru email-uri
    - Error handling și retry logic
    - Email spoofing și headers personalizate
    - Multi-threading pentru performance
    """
    
    def __init__(self):
        self.smtp_server = None
        self.logger = logging.getLogger(__name__)
        self.email_queue = Queue()
        self.is_sending = False
        
        # Mapare template-uri disponibile (fișiere locale)
        self.available_templates = {
            'security': 'emails/revolut_security.html',
            'promotion': 'emails/revolut_promotion.html', 
            'update': 'emails/revolut_update.html'
        }
        
        # Rate limiting settings
        self.rate_limit = {
            'emails_per_minute': 30,
            'emails_per_hour': 1000,
            'delay_between_emails': 2  # seconds
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
            use_ssl = current_app.config.get('MAIL_USE_SSL', False)
            
            if not server or not username or not password:
                raise ValueError("Email configuration incomplete. Check MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD")
            
            if use_ssl:
                smtp = smtplib.SMTP_SSL(server, port)
            else:
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
        """
        if template_name in self.available_templates:
            return self.available_templates[template_name]
        
        # Default la security dacă nu găsește
        return self.available_templates['security']
    
    def load_template_content(self, template_path):
        """
        Încarcă conținutul template-ului din fișier
        """
        try:
            # Construiește calea completă către template
            template_dir = os.path.join(current_app.root_path, 'templates')
            full_path = os.path.join(template_dir, template_path)
            
            if not os.path.exists(full_path):
                self.logger.warning(f"Template not found: {full_path}, using fallback")
                return self._get_fallback_template()
            
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.logger.debug(f"Template loaded: {template_path}")
            return content
            
        except Exception as e:
            self.logger.error(f"Error loading template {template_path}: {str(e)}")
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
            <style>
                body { font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; }
                .header { background: #0075eb; color: white; padding: 20px; text-align: center; }
                .content { padding: 20px; }
                .button { background: #0075eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Revolut</h1>
            </div>
            <div class="content">
                <h2>Security Alert</h2>
                <p>Dear {{target_name}},</p>
                <p>We detected suspicious activity on your Revolut account. Please verify your identity immediately.</p>
                <p><a href="{{tracking_link}}" class="button">Verify Account</a></p>
                <p><small>This is an automated message from Revolut Security.</small></p>
                <img src="{{tracking_pixel}}" width="1" height="1" alt="" />
            </div>
        </body>
        </html>
        '''
    
    def render_email_template(self, template_name, target, campaign, personalization_data=None):
        """
        Renderizează template-ul email cu datele target-ului și campaniei
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
                'tracking_pixel_url': build_tracking_pixel_url(campaign.id, target.id),
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
            
            # Adaugă personalizare din Ollama dacă există
            if personalization_data:
                template_data.update(personalization_data)
            
            # Renderizează template-ul cu Jinja2
            template = Template(template_content)
            rendered_content = template.render(**template_data)
            
            # Extrage subiectul din template
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
            'security': 'Security Alert: Immediate Action Required - {{target_first_name}}',
            'promotion': 'Exclusive Offer: {{target_first_name}}, Don\'t Miss Out!',
            'update': 'Important: Account Update Required - {{target_first_name}}'
        }
        
        return default_subjects.get(template_name, 'Important Message from Revolut - {{target_first_name}}')
    
    def create_email_message(self, target, subject, content, from_email=None, from_name=None, 
                           campaign_id=None, additional_headers=None):
        """
        Creează mesajul email complet cu headers personalizate
        """
        try:
            # Creează mesajul multipart
            msg = MIMEMultipart('alternative')
            
            # Headers principale
            msg['Subject'] = subject
            msg['From'] = from_email or current_app.config.get('MAIL_DEFAULT_SENDER')
            msg['To'] = target.email
            
            # Headers pentru tracking și spoofing
            msg['Message-ID'] = f"<{campaign_id}.{target.id}.{datetime.now().timestamp()}@revolut.com>"
            msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
            
            # Headers de spoofing pentru a părea oficial
            if from_name:
                msg['From'] = f"{from_name} <{from_email or current_app.config.get('MAIL_DEFAULT_SENDER')}>"
            
            # Reply-To pentru a intercepta răspunsurile
            msg['Reply-To'] = 'noreply@revolut.com'
            
            # Headers pentru tracking
            if campaign_id:
                msg['X-Campaign-ID'] = str(campaign_id)
                msg['X-Target-ID'] = str(target.id)
            
            # Headers pentru a evita spam filters
            msg['X-Mailer'] = 'Revolut Notification Service v2.1'
            msg['X-Priority'] = '1'
            msg['Importance'] = 'high'
            
            # Headers suplimentare
            if additional_headers:
                for header, value in additional_headers.items():
                    msg[header] = value
            
            # Adaugă conținutul HTML
            html_part = MIMEText(content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Opțional: adaugă versiunea text plain
            text_content = self._html_to_text(content)
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            msg.attach(text_part)
            
            return msg
            
        except Exception as e:
            self.logger.error(f"Error creating email message: {str(e)}")
            raise
    
    def _html_to_text(self, html_content):
        """
        Convertește HTML-ul în text simplu pentru versiunea text a email-ului
        """
        import re
        
        # Elimină tag-urile HTML
        text = re.sub(r'<[^>]+>', '', html_content)
        
        # Înlocuiește entitățile HTML
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        
        # Curăță spațiile extra
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def send_phishing_email(self, campaign_id, target_id, template_name='security', 
                          personalization_data=None, custom_headers=None):
        """
        Trimite un email de phishing către o țintă specifică
        """
        try:
            # Încarcă entitățile
            campaign = db.session.get(Campaign, campaign_id)
            if not campaign:
                raise ValidationError(f"Campaign {campaign_id} not found")
            
            target = db.session.get(Target, target_id)
            if not target:
                raise ValidationError(f"Target {target_id} not found")
            
            # Validează email-ul țintei
            validate_email(target.email)
            
            # Verifică dacă template-ul există
            if template_name not in self.available_templates:
                self.logger.warning(f"Template {template_name} not found, using security template")
                template_name = 'security'
            
            # Folosește Ollama pentru personalizare dacă este disponibil
            if not personalization_data:
                try:
                    from services.ollama_service import OllamaService
                    ollama = OllamaService()
                    personalization_data = ollama.personalize_email_content(target, campaign, template_name)
                except Exception as e:
                    self.logger.warning(f"Ollama personalization failed: {str(e)}")
                    personalization_data = {}
            
            # Renderizează template-ul
            subject, content = self.render_email_template(template_name, target, campaign, personalization_data)
            
            # Creează mesajul email cu headers personalizate
            email_headers = {
                'X-Template': template_name,
                'X-Mailer': 'Microsoft Outlook 16.0',
                'User-Agent': 'Microsoft-MacOutlook/16.67.22101101'
            }
            
            if custom_headers:
                email_headers.update(custom_headers)
            
            msg = self.create_email_message(
                target=target,
                subject=subject,
                content=content,
                from_email='security@revolut.com',
                from_name='Revolut Security Team',
                campaign_id=campaign.id,
                additional_headers=email_headers
            )
            
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
                    'email_length': len(content),
                    'personalized': bool(personalization_data)
                }
            )
            
            self.logger.info(f"Phishing email sent: {target.email} (Template: {template_name})")
            log_security_event('email_sent', f"Phishing email sent to {target.email}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send phishing email: {str(e)}")
            raise
    
    def send_campaign_emails(self, campaign_id, template_name='security', batch_size=10, 
                           delay_seconds=5, use_threading=True):
        """
        Trimite email-uri pentru întreaga campanie în batch-uri cu threading
        """
        try:
            campaign = db.session.get(Campaign, campaign_id)
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
            
            if use_threading:
                return self._send_emails_threaded(campaign, targets, template_name, batch_size, delay_seconds)
            else:
                return self._send_emails_sequential(campaign, targets, template_name, batch_size, delay_seconds)
            
        except Exception as e:
            self.logger.error(f"Failed to send campaign emails: {str(e)}")
            raise
    
    def _send_emails_threaded(self, campaign, targets, template_name, batch_size, delay_seconds):
        """
        Trimite email-uri folosind threading pentru performanță
        """
        import concurrent.futures
        
        stats = {'sent': 0, 'failed': 0, 'skipped': 0}
        
        # Creează thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # Procesează în batch-uri
            for i in range(0, len(targets), batch_size):
                batch = targets[i:i + batch_size]
                
                # Submit tasks pentru batch-ul curent
                future_to_target = {
                    executor.submit(self._send_single_email_safe, campaign.id, target.id, template_name): target 
                    for target in batch
                }
                
                # Procesează rezultatele
                for future in concurrent.futures.as_completed(future_to_target):
                    target = future_to_target[future]
                    try:
                        success = future.result()
                        if success:
                            stats['sent'] += 1
                        else:
                            stats['failed'] += 1
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
    
    def _send_emails_sequential(self, campaign, targets, template_name, batch_size, delay_seconds):
        """
        Trimite email-uri secvențial (mai sigur, mai lent)
        """
        stats = {'sent': 0, 'failed': 0, 'skipped': 0}
        
        # Procesează în batch-uri
        for i in range(0, len(targets), batch_size):
            batch = targets[i:i + batch_size]
            
            for target in batch:
                try:
                    success = self._send_single_email_safe(campaign.id, target.id, template_name)
                    if success:
                        stats['sent'] += 1
                    else:
                        stats['failed'] += 1
                        
                    # Delay între email-uri individuale
                    time.sleep(self.rate_limit['delay_between_emails'])
                    
                except Exception as e:
                    self.logger.error(f"Failed to send email to {target.email}: {str(e)}")
                    stats['failed'] += 1
            
            # Delay între batch-uri
            if i + batch_size < len(targets):
                self.logger.info(f"Processed batch {i//batch_size + 1}, waiting {delay_seconds}s...")
                time.sleep(delay_seconds)
        
        return stats
    
    def _send_single_email_safe(self, campaign_id, target_id, template_name):
        """
        Wrapper sigur pentru trimiterea unui email individual
        """
        try:
            return self.send_phishing_email(campaign_id, target_id, template_name)
        except Exception as e:
            self.logger.error(f"Error in _send_single_email_safe: {str(e)}")
            return False
    
    def queue_email(self, campaign_id, target_id, template_name='security', priority=1):
        """
        Adaugă un email în queue pentru trimitere asyncronă
        """
        email_job = {
            'campaign_id': campaign_id,
            'target_id': target_id,
            'template_name': template_name,
            'priority': priority,
            'created_at': datetime.now(),
            'retry_count': 0
        }
        
        self.email_queue.put(email_job)
        self.logger.info(f"Email queued for campaign {campaign_id}, target {target_id}")
    
    def process_email_queue(self):
        """
        Procesează queue-ul de email-uri (rulează în background)
        """
        self.is_sending = True
        self.logger.info("Email queue processor started")
        
        while self.is_sending:
            try:
                if not self.email_queue.empty():
                    email_job = self.email_queue.get()
                    
                    try:
                        success = self.send_phishing_email(
                            email_job['campaign_id'],
                            email_job['target_id'],
                            email_job['template_name']
                        )
                        
                        if success:
                            self.logger.info(f"Queued email sent successfully: {email_job}")
                        else:
                            self._handle_failed_email(email_job)
                            
                    except Exception as e:
                        self.logger.error(f"Error processing queued email: {str(e)}")
                        self._handle_failed_email(email_job)
                    
                    # Rate limiting
                    time.sleep(self.rate_limit['delay_between_emails'])
                else:
                    # Queue este gol, așteaptă
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Error in email queue processor: {str(e)}")
                time.sleep(5)
        
        self.logger.info("Email queue processor stopped")
    
    def _handle_failed_email(self, email_job):
        """
        Gestionează email-urile care au eșuat
        """
        email_job['retry_count'] += 1
        
        if email_job['retry_count'] < 3:  # Retry până la 3 ori
            self.logger.warning(f"Retrying failed email: {email_job}")
            # Adaugă înapoi în queue cu delay
            time.sleep(30)
            self.email_queue.put(email_job)
        else:
            self.logger.error(f"Email failed permanently: {email_job}")
    
    def list_available_templates(self):
        """
        Returnează lista template-urilor disponibile
        """
        templates_info = {}
        
        # Template-uri din fișiere
        for name, path in self.available_templates.items():
            templates_info[name] = {
                'name': name.title(),
                'description': f'{name.title()} email template',
                'file': path,
                'type': 'file'
            }
        
        # Template-uri din baza de date
        db_templates = EmailTemplate.query.filter_by(type='email', is_active=True).all()
        for template in db_templates:
            templates_info[f"db_{template.id}"] = {
                'name': template.name,
                'description': template.description or 'Database template',
                'file': None,
                'type': 'database',
                'template_obj': template
            }
        
        return templates_info
    
    def send_test_email(self, template_name, test_email, personalization_data=None):
        """
        Trimite un email de test pentru verificarea template-ului
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
            subject, content = self.render_email_template(template_name, test_target, test_campaign, personalization_data)
            
            # Check if SMTP is configured
            is_configured, config_message = EmailService.validate_email_config()
            
            if not is_configured:
                # Log the test email instead of sending
                self.logger.info(f"Email configuration not complete: {config_message}")
                self.logger.info(f"TEST EMAIL would be sent to {test_email} with subject: [TEST] {subject}")
                self.logger.info(f"Content preview: {content[:200]}...")
                
                # In development/testing, just return True to indicate success
                return True
            
            msg = self.create_email_message(
                target=test_target,
                subject=f"[TEST] {subject}",
                content=content,
                from_email=current_app.config.get('MAIL_DEFAULT_SENDER'),
                additional_headers={'X-Test-Email': 'true'}
            )
            
            smtp = self._get_smtp_connection()
            smtp.send_message(msg)
            smtp.quit()
            
            self.logger.info(f"Test email sent to {test_email} using template {template_name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send test email: {str(e)}")
            raise
    
    def get_email_statistics(self, campaign_id=None):
        """
        Returnează statistici despre email-urile trimise
        """
        try:
            from sqlalchemy import func
            
            # Total email-uri trimise
            query = db.session.query(
                func.count(Tracking.id).label('total_sent')
            ).filter(Tracking.event_type == 'email_sent')
            
            if campaign_id:
                query = query.filter(Tracking.campaign_id == campaign_id)
            
            total_sent = query.scalar() or 0
            
            # Email-uri deschise
            opens_query = db.session.query(
                func.count(Tracking.id).label('total_opens')
            ).filter(Tracking.event_type == 'email_opened')
            
            if campaign_id:
                opens_query = opens_query.filter(Tracking.campaign_id == campaign_id)
            
            total_opens = opens_query.scalar() or 0
            
            # Click-uri din email-uri
            clicks_query = db.session.query(
                func.count(Tracking.id).label('total_clicks')
            ).filter(Tracking.event_type == 'link_clicked')
            
            if campaign_id:
                clicks_query = clicks_query.filter(Tracking.campaign_id == campaign_id)
            
            total_clicks = clicks_query.scalar() or 0
            
            # Calculează ratele
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
    
    def stop_queue_processor(self):
        """
        Oprește procesorul de queue
        """
        self.is_sending = False
        
    @staticmethod
    def validate_email_config():
        """
        Validează configurația email din Flask config
        
        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            # Check required configurations
            server = current_app.config.get('MAIL_SERVER')
            username = current_app.config.get('MAIL_USERNAME')
            password = current_app.config.get('MAIL_PASSWORD')
            
            if not server:
                return False, "Missing MAIL_SERVER configuration"
            
            if not username:
                return False, "Missing MAIL_USERNAME configuration"
            
            if not password:
                return False, "Missing MAIL_PASSWORD configuration"
            
            # Validate email format for username
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, username):
                return False, f"Invalid MAIL_USERNAME format: {username}. Must be a valid email address"
            
            # Validate port
            port = current_app.config.get('MAIL_PORT')
            if port:
                try:
                    port = int(port)
                    if port < 1 or port > 65535:
                        return False, f"Invalid MAIL_PORT: {port}. Must be between 1 and 65535"
                except ValueError:
                    return False, f"Invalid MAIL_PORT: {port}. Must be a number"
            
            # Validate TLS/SSL configuration
            use_tls = current_app.config.get('MAIL_USE_TLS', False)
            use_ssl = current_app.config.get('MAIL_USE_SSL', False)
            
            if use_tls and use_ssl:
                return False, "Cannot use both MAIL_USE_TLS and MAIL_USE_SSL. Choose one"
            
            # Port validation based on encryption
            if port:
                if use_ssl and port not in [465, 993, 995]:
                    return False, f"Port {port} is unusual for SSL. Common SSL ports: 465 (SMTP), 993 (IMAP), 995 (POP3)"
                
                if use_tls and port not in [25, 587, 143, 110]:
                    return False, f"Port {port} is unusual for TLS. Common TLS ports: 587 (SMTP), 143 (IMAP), 110 (POP3)"
            
            # Test actual SMTP connection
            try:
                service = EmailService()
                smtp = service._get_smtp_connection()
                smtp.quit()
                return True, "Email configuration is valid and SMTP connection successful"
            except Exception as e:
                return False, f"SMTP connection failed: {str(e)}"
            
        except Exception as e:
            return False, f"Email configuration validation error: {str(e)}"