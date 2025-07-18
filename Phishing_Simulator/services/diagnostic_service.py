import logging
import smtplib
import requests
import time
from datetime import datetime
from flask import current_app
from typing import Dict, List, Tuple

from services.email_service import EmailService
from services.sms_service import SMSService
from utils.database import db
from utils.helpers import log_security_event


class DiagnosticService:
    """
    Service pentru diagnosticarea și verificarea configurației serviciilor SMS și Email
    
    Features:
    - Verificarea configurației email (SMTP)
    - Testarea conectivității la providerul email
    - Verificarea configurației SMS (Twilio/Nexmo)
    - Testarea conectivității la providerul SMS
    - Rapoarte de diagnostic detaliate
    - Status în timp real al serviciilor
    - Funcții de test complete
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def run_full_diagnostics(self) -> Dict:
        """
        Rulează toate diagnosticele și returnează un raport complet
        
        Returns:
            Dict: Raport de diagnostic complet
        """
        try:
            start_time = datetime.utcnow()
            
            diagnostic_report = {
                'timestamp': start_time.isoformat(),
                'overall_status': 'unknown',
                'email': self.diagnose_email_service(),
                'sms': self.diagnose_sms_service(),
                'database': self.diagnose_database(),
                'configuration': self.diagnose_configuration(),
                'connectivity': self.diagnose_connectivity()
            }
            
            # Determină statusul general
            services_status = [
                diagnostic_report['email']['status'],
                diagnostic_report['sms']['status'],
                diagnostic_report['database']['status']
            ]
            
            if all(status == 'healthy' for status in services_status):
                diagnostic_report['overall_status'] = 'healthy'
            elif any(status == 'error' for status in services_status):
                diagnostic_report['overall_status'] = 'error'
            else:
                diagnostic_report['overall_status'] = 'warning'
            
            # Calculează timpul de execuție
            end_time = datetime.utcnow()
            diagnostic_report['execution_time'] = (end_time - start_time).total_seconds()
            
            self.logger.info(f"Full diagnostics completed in {diagnostic_report['execution_time']:.2f}s")
            log_security_event('diagnostics_run', 'Full diagnostics executed')
            
            return diagnostic_report
            
        except Exception as e:
            self.logger.error(f"Error running full diagnostics: {str(e)}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'overall_status': 'error',
                'error': str(e),
                'execution_time': 0
            }
    
    def diagnose_email_service(self) -> Dict:
        """
        Diagnostichează serviciul de email
        
        Returns:
            Dict: Rezultatul diagnosticului email
        """
        try:
            email_diagnosis = {
                'service': 'email',
                'status': 'unknown',
                'checks': [],
                'configuration': {},
                'recommendations': []
            }
            
            # 1. Verifică configurația de bază
            config_check = self._check_email_configuration()
            email_diagnosis['checks'].append(config_check)
            email_diagnosis['configuration'] = config_check.get('details', {})
            
            # 2. Testează conectivitatea SMTP
            smtp_check = self._test_smtp_connectivity()
            email_diagnosis['checks'].append(smtp_check)
            
            # 3. Testează autentificarea
            auth_check = self._test_smtp_authentication()
            email_diagnosis['checks'].append(auth_check)
            
            # 4. Verifică template-urile disponibile
            template_check = self._check_email_templates()
            email_diagnosis['checks'].append(template_check)
            
            # Determină statusul general al serviciului email
            failed_checks = [check for check in email_diagnosis['checks'] if check['status'] == 'error']
            warning_checks = [check for check in email_diagnosis['checks'] if check['status'] == 'warning']
            
            if failed_checks:
                email_diagnosis['status'] = 'error'
                email_diagnosis['recommendations'].extend([
                    'Check email configuration in environment variables',
                    'Verify SMTP server settings and credentials',
                    'Ensure firewall allows SMTP connections'
                ])
            elif warning_checks:
                email_diagnosis['status'] = 'warning'
                email_diagnosis['recommendations'].extend([
                    'Consider improving email configuration',
                    'Review template setup'
                ])
            else:
                email_diagnosis['status'] = 'healthy'
            
            return email_diagnosis
            
        except Exception as e:
            self.logger.error(f"Error diagnosing email service: {str(e)}")
            return {
                'service': 'email',
                'status': 'error',
                'error': str(e),
                'checks': [],
                'recommendations': ['Fix email service configuration errors']
            }
    
    def diagnose_sms_service(self) -> Dict:
        """
        Diagnostichează serviciul SMS
        
        Returns:
            Dict: Rezultatul diagnosticului SMS
        """
        try:
            sms_diagnosis = {
                'service': 'sms',
                'status': 'unknown',
                'checks': [],
                'configuration': {},
                'recommendations': []
            }
            
            # 1. Verifică configurația SMS
            config_check = self._check_sms_configuration()
            sms_diagnosis['checks'].append(config_check)
            sms_diagnosis['configuration'] = config_check.get('details', {})
            
            # 2. Detectează providerul
            provider_check = self._detect_sms_provider()
            sms_diagnosis['checks'].append(provider_check)
            
            # 3. Testează conectivitatea la provider
            connectivity_check = self._test_sms_provider_connectivity()
            sms_diagnosis['checks'].append(connectivity_check)
            
            # 4. Verifică template-urile SMS
            template_check = self._check_sms_templates()
            sms_diagnosis['checks'].append(template_check)
            
            # Determină statusul general
            failed_checks = [check for check in sms_diagnosis['checks'] if check['status'] == 'error']
            warning_checks = [check for check in sms_diagnosis['checks'] if check['status'] == 'warning']
            
            if failed_checks:
                sms_diagnosis['status'] = 'error'
                sms_diagnosis['recommendations'].extend([
                    'Configure SMS API credentials',
                    'Verify SMS provider settings',
                    'Check API key validity'
                ])
            elif warning_checks:
                sms_diagnosis['status'] = 'warning'
                sms_diagnosis['recommendations'].extend([
                    'Consider improving SMS configuration',
                    'Review provider settings'
                ])
            else:
                sms_diagnosis['status'] = 'healthy'
            
            return sms_diagnosis
            
        except Exception as e:
            self.logger.error(f"Error diagnosing SMS service: {str(e)}")
            return {
                'service': 'sms',
                'status': 'error',
                'error': str(e),
                'checks': [],
                'recommendations': ['Fix SMS service configuration errors']
            }
    
    def diagnose_database(self) -> Dict:
        """
        Diagnostichează conexiunea la baza de date
        
        Returns:
            Dict: Rezultatul diagnosticului database
        """
        try:
            db_diagnosis = {
                'service': 'database',
                'status': 'unknown',
                'checks': [],
                'configuration': {},
                'recommendations': []
            }
            
            # 1. Verifică conexiunea la DB
            connection_check = self._test_database_connection()
            db_diagnosis['checks'].append(connection_check)
            
            # 2. Verifică tabelele
            tables_check = self._check_database_tables()
            db_diagnosis['checks'].append(tables_check)
            
            # 3. Verifică performanța
            performance_check = self._test_database_performance()
            db_diagnosis['checks'].append(performance_check)
            
            # Statusul general
            if any(check['status'] == 'error' for check in db_diagnosis['checks']):
                db_diagnosis['status'] = 'error'
                db_diagnosis['recommendations'].append('Fix database connection issues')
            elif any(check['status'] == 'warning' for check in db_diagnosis['checks']):
                db_diagnosis['status'] = 'warning'
                db_diagnosis['recommendations'].append('Monitor database performance')
            else:
                db_diagnosis['status'] = 'healthy'
            
            return db_diagnosis
            
        except Exception as e:
            self.logger.error(f"Error diagnosing database: {str(e)}")
            return {
                'service': 'database',
                'status': 'error',
                'error': str(e),
                'checks': [],
                'recommendations': ['Fix database configuration']
            }
    
    def diagnose_configuration(self) -> Dict:
        """
        Verifică configurația generală a aplicației
        """
        try:
            config_diagnosis = {
                'checks': [],
                'missing_configs': [],
                'recommendations': []
            }
            
            # Configurații critice
            critical_configs = [
                'SECRET_KEY',
                'BASE_URL',
                'MAIL_SERVER',
                'MAIL_USERNAME'
            ]
            
            # Configurații opționale
            optional_configs = [
                'SMS_API_KEY',
                'OLLAMA_BASE_URL',
                'WEBHOOK_SECRET'
            ]
            
            for config in critical_configs:
                if not current_app.config.get(config):
                    config_diagnosis['missing_configs'].append(config)
            
            # Verifică configurația de securitate
            if current_app.config.get('SECRET_KEY') == 'dev-secret-key-change-in-production':
                config_diagnosis['recommendations'].append('Change SECRET_KEY in production')
            
            if not current_app.config.get('SESSION_COOKIE_SECURE') and not current_app.debug:
                config_diagnosis['recommendations'].append('Enable SESSION_COOKIE_SECURE in production')
            
            return config_diagnosis
            
        except Exception as e:
            self.logger.error(f"Error diagnosing configuration: {str(e)}")
            return {'error': str(e)}
    
    def diagnose_connectivity(self) -> Dict:
        """
        Testează conectivitatea la servicii externe
        """
        try:
            connectivity_tests = []
            
            # Test conectivitate la Ollama (dacă e configurat)
            ollama_url = current_app.config.get('OLLAMA_BASE_URL')
            if ollama_url:
                connectivity_tests.append(self._test_ollama_connectivity())
            
            return {
                'external_services': connectivity_tests
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _check_email_configuration(self) -> Dict:
        """Verifică configurația email"""
        try:
            required_configs = ['MAIL_SERVER', 'MAIL_USERNAME', 'MAIL_PASSWORD']
            missing_configs = []
            
            for config in required_configs:
                if not current_app.config.get(config):
                    missing_configs.append(config)
            
            if missing_configs:
                return {
                    'name': 'Email Configuration',
                    'status': 'error',
                    'message': f'Missing configurations: {", ".join(missing_configs)}',
                    'details': {'missing': missing_configs}
                }
            
            # Extrage configurația (fără a expune credențialele)
            config_details = {
                'server': current_app.config.get('MAIL_SERVER'),
                'port': current_app.config.get('MAIL_PORT'),
                'use_tls': current_app.config.get('MAIL_USE_TLS'),
                'use_ssl': current_app.config.get('MAIL_USE_SSL'),
                'username': current_app.config.get('MAIL_USERNAME'),
                'default_sender': current_app.config.get('MAIL_DEFAULT_SENDER')
            }
            
            return {
                'name': 'Email Configuration',
                'status': 'success',
                'message': 'Email configuration is complete',
                'details': config_details
            }
            
        except Exception as e:
            return {
                'name': 'Email Configuration',
                'status': 'error',
                'message': str(e)
            }
    
    def _test_smtp_connectivity(self) -> Dict:
        """Testează conectivitatea SMTP"""
        try:
            server = current_app.config.get('MAIL_SERVER')
            port = current_app.config.get('MAIL_PORT', 587)
            use_ssl = current_app.config.get('MAIL_USE_SSL', False)
            use_tls = current_app.config.get('MAIL_USE_TLS', True)
            
            if not server:
                return {
                    'name': 'SMTP Connectivity',
                    'status': 'error',
                    'message': 'MAIL_SERVER not configured'
                }
            
            start_time = time.time()
            
            if use_ssl:
                smtp = smtplib.SMTP_SSL(server, port, timeout=10)
            else:
                smtp = smtplib.SMTP(server, port, timeout=10)
                smtp.ehlo()
                if use_tls:
                    smtp.starttls()
                    smtp.ehlo()
            
            smtp.quit()
            connection_time = (time.time() - start_time) * 1000
            
            return {
                'name': 'SMTP Connectivity',
                'status': 'success',
                'message': f'Successfully connected to {server}:{port}',
                'details': {
                    'server': server,
                    'port': port,
                    'connection_time_ms': round(connection_time, 2)
                }
            }
            
        except Exception as e:
            return {
                'name': 'SMTP Connectivity',
                'status': 'error',
                'message': f'Failed to connect to SMTP server: {str(e)}'
            }
    
    def _test_smtp_authentication(self) -> Dict:
        """Testează autentificarea SMTP"""
        try:
            # Folosește EmailService pentru testare
            is_valid, message = EmailService.validate_email_config()
            
            if is_valid:
                return {
                    'name': 'SMTP Authentication',
                    'status': 'success',
                    'message': 'SMTP authentication successful'
                }
            else:
                return {
                    'name': 'SMTP Authentication',
                    'status': 'error',
                    'message': message
                }
                
        except Exception as e:
            return {
                'name': 'SMTP Authentication',
                'status': 'error',
                'message': f'Authentication test failed: {str(e)}'
            }
    
    def _check_email_templates(self) -> Dict:
        """Verifică template-urile email"""
        try:
            email_service = EmailService()
            templates = email_service.list_available_templates()
            
            if not templates:
                return {
                    'name': 'Email Templates',
                    'status': 'warning',
                    'message': 'No email templates found'
                }
            
            return {
                'name': 'Email Templates',
                'status': 'success',
                'message': f'Found {len(templates)} email templates',
                'details': {'template_count': len(templates), 'templates': list(templates.keys())}
            }
            
        except Exception as e:
            return {
                'name': 'Email Templates',
                'status': 'error',
                'message': str(e)
            }
    
    def _check_sms_configuration(self) -> Dict:
        """Verifică configurația SMS"""
        try:
            sms_configs = ['SMS_API_KEY', 'SMS_FROM_NUMBER']
            missing_configs = []
            
            for config in sms_configs:
                if not current_app.config.get(config):
                    missing_configs.append(config)
            
            if missing_configs:
                return {
                    'name': 'SMS Configuration',
                    'status': 'warning',
                    'message': f'SMS not fully configured: {", ".join(missing_configs)} missing',
                    'details': {'missing': missing_configs}
                }
            
            config_details = {
                'api_key_set': bool(current_app.config.get('SMS_API_KEY')),
                'from_number': current_app.config.get('SMS_FROM_NUMBER'),
                'api_secret_set': bool(current_app.config.get('SMS_API_SECRET'))
            }
            
            return {
                'name': 'SMS Configuration',
                'status': 'success',
                'message': 'SMS configuration is complete',
                'details': config_details
            }
            
        except Exception as e:
            return {
                'name': 'SMS Configuration',
                'status': 'error',
                'message': str(e)
            }
    
    def _detect_sms_provider(self) -> Dict:
        """Detectează providerul SMS"""
        try:
            sms_service = SMSService()
            provider = sms_service.provider
            
            return {
                'name': 'SMS Provider Detection',
                'status': 'success',
                'message': f'Detected SMS provider: {provider}',
                'details': {'provider': provider}
            }
            
        except Exception as e:
            return {
                'name': 'SMS Provider Detection',
                'status': 'error',
                'message': str(e)
            }
    
    def _test_sms_provider_connectivity(self) -> Dict:
        """Testează conectivitatea la providerul SMS"""
        try:
            sms_service = SMSService()
            
            if sms_service.provider == 'mock':
                return {
                    'name': 'SMS Provider Connectivity',
                    'status': 'warning',
                    'message': 'Using mock SMS provider (development mode)'
                }
            
            # Pentru Twilio sau Nexmo, testăm conectivitatea
            if sms_service.provider == 'twilio':
                return self._test_twilio_connectivity()
            elif sms_service.provider == 'nexmo':
                return self._test_nexmo_connectivity()
            
            return {
                'name': 'SMS Provider Connectivity',
                'status': 'success',
                'message': f'Provider {sms_service.provider} detected'
            }
            
        except Exception as e:
            return {
                'name': 'SMS Provider Connectivity',
                'status': 'error',
                'message': str(e)
            }
    
    def _test_twilio_connectivity(self) -> Dict:
        """Testează conectivitatea Twilio"""
        try:
            account_sid = current_app.config.get('SMS_API_KEY')
            auth_token = current_app.config.get('SMS_API_SECRET')
            
            if not account_sid or not auth_token:
                return {
                    'name': 'SMS Provider Connectivity',
                    'status': 'error',
                    'message': 'Twilio credentials not configured'
                }
            
            # Test API call la Twilio
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}.json"
            
            start_time = time.time()
            response = requests.get(url, auth=(account_sid, auth_token), timeout=10)
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return {
                    'name': 'SMS Provider Connectivity',
                    'status': 'success',
                    'message': 'Twilio API connection successful',
                    'details': {
                        'provider': 'twilio',
                        'response_time_ms': round(response_time, 2)
                    }
                }
            else:
                return {
                    'name': 'SMS Provider Connectivity',
                    'status': 'error',
                    'message': f'Twilio API error: {response.status_code}'
                }
                
        except Exception as e:
            return {
                'name': 'SMS Provider Connectivity',
                'status': 'error',
                'message': f'Twilio connectivity test failed: {str(e)}'
            }
    
    def _test_nexmo_connectivity(self) -> Dict:
        """Testează conectivitatea Nexmo/Vonage"""
        try:
            api_key = current_app.config.get('SMS_API_KEY')
            api_secret = current_app.config.get('SMS_API_SECRET')
            
            if not api_key or not api_secret:
                return {
                    'name': 'SMS Provider Connectivity',
                    'status': 'error',
                    'message': 'Nexmo credentials not configured'
                }
            
            # Test API call la Nexmo
            url = "https://rest.nexmo.com/account/get-balance"
            params = {'api_key': api_key, 'api_secret': api_secret}
            
            start_time = time.time()
            response = requests.get(url, params=params, timeout=10)
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return {
                    'name': 'SMS Provider Connectivity',
                    'status': 'success',
                    'message': 'Nexmo API connection successful',
                    'details': {
                        'provider': 'nexmo',
                        'response_time_ms': round(response_time, 2)
                    }
                }
            else:
                return {
                    'name': 'SMS Provider Connectivity',
                    'status': 'error',
                    'message': f'Nexmo API error: {response.status_code}'
                }
                
        except Exception as e:
            return {
                'name': 'SMS Provider Connectivity',
                'status': 'error',
                'message': f'Nexmo connectivity test failed: {str(e)}'
            }
    
    def _check_sms_templates(self) -> Dict:
        """Verifică template-urile SMS"""
        try:
            from models.template import Template
            
            sms_templates = Template.query.filter_by(type='sms', is_active=True).count()
            
            return {
                'name': 'SMS Templates',
                'status': 'success' if sms_templates > 0 else 'warning',
                'message': f'Found {sms_templates} SMS templates',
                'details': {'template_count': sms_templates}
            }
            
        except Exception as e:
            return {
                'name': 'SMS Templates',
                'status': 'error',
                'message': str(e)
            }
    
    def _test_database_connection(self) -> Dict:
        """Testează conexiunea la baza de date"""
        try:
            start_time = time.time()
            with db.engine.connect() as connection:
                connection.execute(db.text("SELECT 1"))
            connection_time = (time.time() - start_time) * 1000
            
            return {
                'name': 'Database Connection',
                'status': 'success',
                'message': 'Database connection successful',
                'details': {
                    'connection_time_ms': round(connection_time, 2),
                    'database_url': current_app.config.get('SQLALCHEMY_DATABASE_URI', '').split('@')[-1] if '@' in current_app.config.get('SQLALCHEMY_DATABASE_URI', '') else 'sqlite'
                }
            }
            
        except Exception as e:
            return {
                'name': 'Database Connection',
                'status': 'error',
                'message': f'Database connection failed: {str(e)}'
            }
    
    def _check_database_tables(self) -> Dict:
        """Verifică tabelele din baza de date"""
        try:
            from sqlalchemy import inspect
            
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            expected_tables = ['campaigns', 'targets', 'templates', 'tracking', 'credentials']
            missing_tables = [table for table in expected_tables if table not in tables]
            
            if missing_tables:
                return {
                    'name': 'Database Tables',
                    'status': 'error',
                    'message': f'Missing tables: {", ".join(missing_tables)}',
                    'details': {'missing_tables': missing_tables, 'found_tables': tables}
                }
            
            return {
                'name': 'Database Tables',
                'status': 'success',
                'message': f'All {len(expected_tables)} required tables found',
                'details': {'table_count': len(tables), 'tables': tables}
            }
            
        except Exception as e:
            return {
                'name': 'Database Tables',
                'status': 'error',
                'message': str(e)
            }
    
    def _test_database_performance(self) -> Dict:
        """Testează performanța bazei de date"""
        try:
            from models.campaign import Campaign
            
            start_time = time.time()
            campaign_count = Campaign.query.count()
            query_time = (time.time() - start_time) * 1000
            
            status = 'success'
            if query_time > 1000:  # Peste 1 secundă
                status = 'warning'
            
            return {
                'name': 'Database Performance',
                'status': status,
                'message': f'Query executed in {query_time:.2f}ms',
                'details': {
                    'query_time_ms': round(query_time, 2),
                    'record_count': campaign_count
                }
            }
            
        except Exception as e:
            return {
                'name': 'Database Performance',
                'status': 'error',
                'message': str(e)
            }
    
    def _test_ollama_connectivity(self) -> Dict:
        """Testează conectivitatea la Ollama"""
        try:
            ollama_url = current_app.config.get('OLLAMA_BASE_URL')
            
            start_time = time.time()
            response = requests.get(f"{ollama_url}/api/tags", timeout=5)
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return {
                    'name': 'Ollama Connectivity',
                    'status': 'success',
                    'message': 'Ollama API accessible',
                    'details': {
                        'url': ollama_url,
                        'response_time_ms': round(response_time, 2)
                    }
                }
            else:
                return {
                    'name': 'Ollama Connectivity',
                    'status': 'warning',
                    'message': f'Ollama API returned {response.status_code}'
                }
                
        except Exception as e:
            return {
                'name': 'Ollama Connectivity',
                'status': 'warning',
                'message': f'Ollama not accessible: {str(e)}'
            }
    
    def send_test_email(self, test_email: str, template_name: str = 'security') -> Dict:
        """
        Trimite un email de test și returnează rezultatul
        
        Args:
            test_email: Adresa de email pentru test
            template_name: Template-ul de utilizat
            
        Returns:
            Dict: Rezultatul testului
        """
        try:
            email_service = EmailService()
            
            success = email_service.send_test_email(template_name, test_email)
            
            if success:
                return {
                    'status': 'success',
                    'message': f'Test email sent successfully to {test_email}',
                    'timestamp': datetime.utcnow().isoformat(),
                    'details': {
                        'recipient': test_email,
                        'template': template_name
                    }
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Test email sending failed',
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Test email failed: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def send_test_sms(self, test_phone: str, template_content: str = None) -> Dict:
        """
        Trimite un SMS de test și returnează rezultatul
        
        Args:
            test_phone: Numărul de telefon pentru test
            template_content: Conținutul template-ului SMS
            
        Returns:
            Dict: Rezultatul testului
        """
        try:
            sms_service = SMSService()
            
            if not template_content:
                template_content = "TEST: This is a test SMS from Phishing Simulator diagnostic. Provider: {{company_name}}"
            
            success = sms_service.send_test_sms(template_content, test_phone)
            
            if success:
                return {
                    'status': 'success',
                    'message': f'Test SMS sent successfully to {test_phone}',
                    'timestamp': datetime.utcnow().isoformat(),
                    'details': {
                        'recipient': test_phone,
                        'provider': sms_service.provider
                    }
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Test SMS sending failed',
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Test SMS failed: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def get_service_status_summary(self) -> Dict:
        """
        Returnează un rezumat rapid al statusului serviciilor
        
        Returns:
            Dict: Status sumar al serviciilor
        """
        try:
            # Status email
            email_config_valid, email_msg = EmailService.validate_email_config()
            
            # Status SMS
            sms_config_valid, sms_msg = SMSService.validate_sms_config()
            
            # Status database
            try:
                with db.engine.connect() as connection:
                    connection.execute(db.text("SELECT 1"))
                db_status = 'healthy'
                db_msg = 'Database connection OK'
            except Exception as e:
                db_status = 'error'
                db_msg = f'Database error: {str(e)}'
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'services': {
                    'email': {
                        'status': 'healthy' if email_config_valid else 'error',
                        'message': email_msg
                    },
                    'sms': {
                        'status': 'healthy' if sms_config_valid else 'warning',
                        'message': sms_msg
                    },
                    'database': {
                        'status': db_status,
                        'message': db_msg
                    }
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting service status: {str(e)}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'services': {}
            }