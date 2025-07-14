import logging
import requests
import time
from datetime import datetime
from flask import current_app
from jinja2 import Template

from models.campaign import Campaign
from models.target import Target
from models.template import Template as SMSTemplate
from models.tracking import Tracking
from utils.database import db
from utils.helpers import build_tracking_url, get_client_ip, log_security_event
from utils.validators import validate_phone_number, ValidationError


class SMSService:
    """
    Service pentru trimiterea SMS-urilor de phishing
    
    Features:
    - Trimitere SMS prin API (Twilio, etc.)
    - Template-uri personalizate pentru SMS
    - Link scurtat cu tracking
    - Batch sending cu rate limiting
    - Integrare cu TrackingService
    - Support pentru multiple providere SMS
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_key = current_app.config.get('SMS_API_KEY')
        self.api_secret = current_app.config.get('SMS_API_SECRET')
        self.from_number = current_app.config.get('SMS_FROM_NUMBER', '+40700000000')
        
        # Provider SMS (Twilio, etc.)
        self.provider = self._detect_sms_provider()
    
    def _detect_sms_provider(self):
        """
        Detectează providerul SMS pe baza configurației
        
        Returns:
            str: Tipul providerului (twilio, nexmo, custom)
        """
        if self.api_key and 'twilio' in str(self.api_key).lower():
            return 'twilio'
        elif self.api_key and 'nexmo' in str(self.api_key).lower():
            return 'nexmo'
        else:
            return 'custom'  # Provider personalizat sau mock
    
    def render_sms_template(self, template_content, target, campaign):
        """
        Renderizează template-ul SMS cu datele target-ului
        
        Args:
            template_content: Conținutul template-ului SMS
            target: Target-ul destinatar
            campaign: Campania asociată
            
        Returns:
            str: SMS-ul renderizat
        """
        try:
            # Pregătește datele pentru template
            template_data = {
                # Target data
                'target_name': target.display_name,
                'target_first_name': target.first_name or 'User',
                'target_last_name': target.last_name or '',
                'target_phone': target.phone,
                'target_company': target.company or 'Your Company',
                
                # Campaign data
                'campaign_name': campaign.name,
                'campaign_id': campaign.id,
                
                # URLs (link scurtat pentru SMS)
                'tracking_link': build_tracking_url(campaign.id, target.id, 'login'),
                'short_link': self._create_short_link(campaign.id, target.id),
                
                # Date
                'current_date': datetime.now().strftime('%Y-%m-%d'),
                'current_time': datetime.now().strftime('%H:%M'),
                
                # Branding
                'company_name': 'Revolut',
                'support_number': '+40312345678'
            }
            
            # Renderizează template-ul
            template = Template(template_content)
            rendered_sms = template.render(**template_data)
            
            # Verifică lungimea SMS-ului (max 160 caractere pentru SMS standard)
            if len(rendered_sms) > 160:
                self.logger.warning(f"SMS too long ({len(rendered_sms)} chars): {rendered_sms[:50]}...")
            
            self.logger.debug(f"SMS template rendered for {target.phone}")
            return rendered_sms
            
        except Exception as e:
            self.logger.error(f"Error rendering SMS template: {str(e)}")
            raise
    
    def _create_short_link(self, campaign_id, target_id):
        """
        Creează link scurtat pentru SMS (pentru a economisi caractere)
        
        Args:
            campaign_id: ID-ul campaniei
            target_id: ID-ul țintei
            
        Returns:
            str: Link scurtat
        """
        # În practică, ai folosi un serviciu de URL shortening (bit.ly, tinyurl)
        # Pentru demo, facem un link "scurt" intern
        base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
        short_path = f"/r/{campaign_id}/{target_id}"
        return f"{base_url}{short_path}"
    
    def send_sms_twilio(self, to_phone, message):
        """
        Trimite SMS prin Twilio API
        
        Args:
            to_phone: Numărul destinatar
            message: Mesajul SMS
            
        Returns:
            dict: Răspunsul de la Twilio
        """
        try:
            # Twilio API endpoint
            account_sid = self.api_key  # Pentru Twilio, API_KEY = Account SID
            auth_token = self.api_secret
            
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            
            data = {
                'From': self.from_number,
                'To': to_phone,
                'Body': message
            }
            
            response = requests.post(
                url,
                data=data,
                auth=(account_sid, auth_token),
                timeout=30
            )
            
            if response.status_code == 201:
                result = response.json()
                self.logger.info(f"SMS sent via Twilio to {to_phone}: {result.get('sid')}")
                return {'success': True, 'message_id': result.get('sid'), 'provider': 'twilio'}
            else:
                error_msg = f"Twilio error {response.status_code}: {response.text}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            self.logger.error(f"Twilio SMS failed: {str(e)}")
            raise
    
    def send_sms_nexmo(self, to_phone, message):
        """
        Trimite SMS prin Nexmo/Vonage API
        
        Args:
            to_phone: Numărul destinatar
            message: Mesajul SMS
            
        Returns:
            dict: Răspunsul de la Nexmo
        """
        try:
            url = "https://rest.nexmo.com/sms/json"
            
            data = {
                'api_key': self.api_key,
                'api_secret': self.api_secret,
                'from': self.from_number,
                'to': to_phone.replace('+', ''),  # Nexmo vrea fără +
                'text': message
            }
            
            response = requests.post(url, data=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result['messages'][0]['status'] == '0':
                    message_id = result['messages'][0]['message-id']
                    self.logger.info(f"SMS sent via Nexmo to {to_phone}: {message_id}")
                    return {'success': True, 'message_id': message_id, 'provider': 'nexmo'}
                else:
                    error_msg = f"Nexmo error: {result['messages'][0]['error-text']}"
                    raise Exception(error_msg)
            else:
                raise Exception(f"Nexmo HTTP error: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Nexmo SMS failed: {str(e)}")
            raise
    
    def send_sms_mock(self, to_phone, message):
        """
        Mock SMS sender pentru development/testing
        
        Args:
            to_phone: Numărul destinatar
            message: Mesajul SMS
            
        Returns:
            dict: Răspuns mock
        """
        import uuid
        
        # Simulează delay de rețea
        time.sleep(0.5)
        
        mock_id = str(uuid.uuid4())[:8]
        
        self.logger.info(f"MOCK SMS to {to_phone}: {message}")
        print(f"\n📱 MOCK SMS SENT:")
        print(f"To: {to_phone}")
        print(f"Message: {message}")
        print(f"Message ID: {mock_id}\n")
        
        return {'success': True, 'message_id': mock_id, 'provider': 'mock'}
    
    def send_sms(self, to_phone, message):
        """
        Trimite SMS folosind providerul configurat
        
        Args:
            to_phone: Numărul destinatar
            message: Mesajul SMS
            
        Returns:
            dict: Rezultatul trimiterii
        """
        try:
            validate_phone_number(to_phone)
            
            if self.provider == 'twilio':
                return self.send_sms_twilio(to_phone, message)
            elif self.provider == 'nexmo':
                return self.send_sms_nexmo(to_phone, message)
            else:
                # Mock/Custom provider
                return self.send_sms_mock(to_phone, message)
                
        except Exception as e:
            self.logger.error(f"SMS sending failed: {str(e)}")
            raise
    
    def send_phishing_sms(self, campaign_id, target_id, template_name='security'):
        """
        Trimite SMS de phishing către o țintă specifică
        
        Args:
            campaign_id: ID-ul campaniei
            target_id: ID-ul țintei
            template_name: Numele template-ului (opțional)
            
        Returns:
            bool: True dacă SMS-ul a fost trimis cu succes
        """
        try:
            # Încarcă entitățile
            campaign = Campaign.query.get(campaign_id)
            if not campaign:
                raise ValidationError(f"Campaign {campaign_id} not found")
            
            target = Target.query.get(target_id)
            if not target:
                raise ValidationError(f"Target {target_id} not found")
            
            if not target.phone:
                raise ValidationError(f"Target {target_id} has no phone number")
            
            # Găsește template-ul SMS
            sms_template = SMSTemplate.query.filter_by(
                type='sms',
                is_active=True
            ).first()
            
            if not sms_template:
                # Template default pentru SMS
                template_content = "REVOLUT ALERT: Suspicious login detected. Verify immediately: {{tracking_link}} Reply STOP to opt out."
            else:
                template_content = sms_template.content
            
            # Renderizează template-ul
            rendered_message = self.render_sms_template(template_content, target, campaign)
            
            # Trimite SMS-ul
            result = self.send_sms(target.phone, rendered_message)
            
            if result['success']:
                # Actualizează statusul țintei
                target.mark_sms_sent()
                
                # Creează eveniment de tracking
                Tracking.create_event(
                    campaign_id=campaign.id,
                    event_type='sms_sent',
                    target_id=target.id,
                    ip_address=get_client_ip(),
                    extra_data={
                        'template_name': template_name,
                        'message_length': len(rendered_message),
                        'provider': result['provider'],
                        'message_id': result['message_id']
                    }
                )
                
                # Incrementează usage pentru template dacă există
                if sms_template:
                    sms_template.increment_usage()
                
                self.logger.info(f"Phishing SMS sent: {target.phone} (Campaign: {campaign.name})")
                log_security_event('sms_sent', f"Phishing SMS sent to {target.phone}")
                
                return True
            else:
                raise Exception("SMS sending failed")
                
        except Exception as e:
            self.logger.error(f"Failed to send phishing SMS: {str(e)}")
            raise
    
    def send_campaign_sms(self, campaign_id, template_name='security', batch_size=5, delay_seconds=10):
        """
        Trimite SMS-uri pentru întreaga campanie în batch-uri
        
        Args:
            campaign_id: ID-ul campaniei
            template_name: Numele template-ului
            batch_size: Numărul de SMS-uri per batch (mai mic decât email)
            delay_seconds: Delay între batch-uri (mai mare pentru SMS)
            
        Returns:
            dict: Statistici despre trimitere
        """
        try:
            campaign = Campaign.query.get(campaign_id)
            if not campaign:
                raise ValidationError(f"Campaign {campaign_id} not found")
            
            if not campaign.is_active:
                raise ValidationError("Campaign must be active to send SMS")
            
            # Găsește țintele cu număr de telefon care nu au primit SMS
            targets = Target.query.filter_by(
                campaign_id=campaign_id,
                sms_sent=False
            ).filter(Target.phone.isnot(None)).all()
            
            if not targets:
                self.logger.warning(f"No targets with phone numbers for campaign {campaign_id}")
                return {'sent': 0, 'failed': 0, 'skipped': 0}
            
            stats = {'sent': 0, 'failed': 0, 'skipped': 0}
            
            # Procesează în batch-uri mici (SMS au rate limiting mai strict)
            for i in range(0, len(targets), batch_size):
                batch = targets[i:i + batch_size]
                
                for target in batch:
                    try:
                        self.send_phishing_sms(campaign_id, target.id, template_name)
                        stats['sent'] += 1
                        
                        # Delay între SMS-uri individuale (pentru rate limiting)
                        time.sleep(1)
                        
                    except Exception as e:
                        self.logger.error(f"Failed to send SMS to {target.phone}: {str(e)}")
                        stats['failed'] += 1
                
                # Delay mai mare între batch-uri
                if i + batch_size < len(targets):
                    self.logger.info(f"Processed SMS batch {i//batch_size + 1}, waiting {delay_seconds}s...")
                    time.sleep(delay_seconds)
            
            self.logger.info(f"Campaign {campaign.name} SMS sending complete: {stats}")
            log_security_event('campaign_sms_sent', f"Campaign {campaign.name}: {stats['sent']} SMS sent")
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to send campaign SMS: {str(e)}")
            raise
    
    def send_test_sms(self, template_content, test_phone):
        """
        Trimite SMS de test pentru verificarea template-ului
        
        Args:
            template_content: Conținutul template-ului
            test_phone: Numărul de telefon pentru test
            
        Returns:
            bool: True dacă SMS-ul de test a fost trimis
        """
        try:
            validate_phone_number(test_phone)
            
            # Creează target fictiv pentru test
            test_target = Target(
                campaign_id=0,
                email="test@example.com",
                phone=test_phone,
                first_name="Test",
                last_name="User"
            )
            
            # Creează campanie fictivă pentru test
            test_campaign = Campaign(
                name="Test Campaign",
                type="sms",
                description="This is a test"
            )
            test_campaign.id = 0
            
            # Renderizează și trimite
            rendered_message = self.render_sms_template(template_content, test_target, test_campaign)
            rendered_message = f"[TEST] {rendered_message}"
            
            result = self.send_sms(test_phone, rendered_message)
            
            self.logger.info(f"Test SMS sent to {test_phone}")
            
            return result['success']
            
        except Exception as e:
            self.logger.error(f"Failed to send test SMS: {str(e)}")
            raise
    
    def get_sms_statistics(self, campaign_id=None):
        """
        Returnează statistici despre SMS-urile trimise
        
        Args:
            campaign_id: ID-ul campaniei (opțional)
            
        Returns:
            dict: Statistici SMS
        """
        try:
            from sqlalchemy import func
            
            # Total SMS-uri trimise
            query = db.session.query(
                func.count(Tracking.id).label('total_sent')
            ).filter(Tracking.event_type == 'sms_sent')
            
            if campaign_id:
                query = query.filter(Tracking.campaign_id == campaign_id)
            
            total_sent = query.scalar() or 0
            
            # Click-uri din SMS
            clicks_query = db.session.query(
                func.count(Tracking.id).label('total_clicks')
            ).filter(Tracking.event_type == 'link_clicked')
            
            if campaign_id:
                clicks_query = clicks_query.filter(Tracking.campaign_id == campaign_id)
            
            total_clicks = clicks_query.scalar() or 0
            
            # Calculează rata de click pentru SMS
            click_rate = (total_clicks / total_sent * 100) if total_sent > 0 else 0
            
            return {
                'total_sent': total_sent,
                'total_clicks': total_clicks,
                'click_rate': round(click_rate, 2)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting SMS statistics: {str(e)}")
            return {}
    
    @staticmethod
    def validate_sms_config():
        """
        Validează configurația SMS din Flask config
        
        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            required_configs = ['SMS_API_KEY', 'SMS_FROM_NUMBER']
            
            for config_key in required_configs:
                if not current_app.config.get(config_key):
                    return False, f"Missing configuration: {config_key}"
            
            return True, "SMS configuration is valid"
            
        except Exception as e:
            return False, f"SMS configuration error: {str(e)}"