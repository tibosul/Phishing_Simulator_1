"""
Service Testing Utilities for SMS and Email Services

This module provides comprehensive testing and validation tools for SMS and Email services,
helping diagnose configuration issues and test connectivity.
"""

import logging
import os
import smtplib
import requests
from datetime import datetime
from flask import current_app
from typing import Dict, Tuple, Any, Optional

from services.sms_service import SMSService
from services.email_service import EmailService


class ServiceTester:
    """
    Comprehensive testing utility for SMS and Email services
    
    Features:
    - Configuration validation
    - Connectivity testing
    - Provider detection
    - Error diagnosis
    - Test message sending
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def test_all_services(self) -> Dict[str, Any]:
        """
        Test all configured services and return comprehensive status
        
        Returns:
            dict: Complete service status report
        """
        try:
            results = {
                'timestamp': datetime.now().isoformat(),
                'sms': self.test_sms_service(),
                'email': self.test_email_service(),
                'summary': {}
            }
            
            # Generate summary
            sms_ok = results['sms']['status'] == 'ok'
            email_ok = results['email']['status'] == 'ok'
            
            results['summary'] = {
                'overall_status': 'ok' if (sms_ok and email_ok) else 'warning' if (sms_ok or email_ok) else 'error',
                'services_working': sum([sms_ok, email_ok]),
                'total_services': 2,
                'issues_found': len([s for s in [results['sms'], results['email']] if s['status'] != 'ok'])
            }
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error testing all services: {str(e)}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'summary': {'overall_status': 'error', 'services_working': 0, 'total_services': 2}
            }
    
    def test_sms_service(self) -> Dict[str, Any]:
        """
        Comprehensive SMS service testing
        
        Returns:
            dict: SMS service status and diagnostics
        """
        try:
            result = {
                'service': 'SMS',
                'timestamp': datetime.now().isoformat(),
                'status': 'unknown',
                'provider': 'unknown',
                'configuration': {},
                'connectivity': {},
                'recommendations': []
            }
            
            # Test configuration
            config_valid, config_message = SMSService.validate_sms_config()
            result['configuration'] = {
                'valid': config_valid,
                'message': config_message,
                'details': self._analyze_sms_config()
            }
            
            if not config_valid:
                result['status'] = 'error'
                result['recommendations'].append('Fix SMS configuration: ' + config_message)
                return result
            
            # Test service initialization
            try:
                sms_service = SMSService()
                result['provider'] = getattr(sms_service, 'provider', 'unknown')
                
                # Test provider-specific connectivity
                if result['provider'] in ['twilio', 'nexmo']:
                    connectivity_result = self._test_sms_connectivity(sms_service)
                    result['connectivity'] = connectivity_result
                    
                    if connectivity_result.get('success', False):
                        result['status'] = 'ok'
                    else:
                        result['status'] = 'error'
                        result['recommendations'].append('SMS provider connectivity failed: ' + 
                                                       connectivity_result.get('error', 'Unknown error'))
                else:
                    # Mock provider
                    result['status'] = 'warning'
                    result['connectivity'] = {'provider': 'mock', 'message': 'Using mock SMS provider'}
                    result['recommendations'].append('Configure real SMS provider (Twilio/Nexmo) for production')
                
            except Exception as e:
                result['status'] = 'error'
                result['recommendations'].append(f'SMS service initialization failed: {str(e)}')
                result['connectivity'] = {'error': str(e)}
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error testing SMS service: {str(e)}")
            return {
                'service': 'SMS',
                'status': 'error',
                'error': str(e),
                'recommendations': ['Fix SMS service testing error: ' + str(e)]
            }
    
    def test_email_service(self) -> Dict[str, Any]:
        """
        Comprehensive Email service testing
        
        Returns:
            dict: Email service status and diagnostics
        """
        try:
            result = {
                'service': 'Email',
                'timestamp': datetime.now().isoformat(),
                'status': 'unknown',
                'provider': 'SMTP',
                'configuration': {},
                'connectivity': {},
                'recommendations': []
            }
            
            # Test configuration
            config_valid, config_message = EmailService.validate_email_config()
            result['configuration'] = {
                'valid': config_valid,
                'message': config_message,
                'details': self._analyze_email_config()
            }
            
            if not config_valid:
                result['status'] = 'error'
                result['recommendations'].append('Fix Email configuration: ' + config_message)
                return result
            
            # Test SMTP connectivity
            try:
                connectivity_result = self._test_smtp_connectivity()
                result['connectivity'] = connectivity_result
                
                if connectivity_result.get('success', False):
                    result['status'] = 'ok'
                else:
                    result['status'] = 'error'
                    result['recommendations'].append('SMTP connectivity failed: ' + 
                                                   connectivity_result.get('error', 'Unknown error'))
                
            except Exception as e:
                result['status'] = 'error'
                result['connectivity'] = {'success': False, 'error': str(e)}
                result['recommendations'].append(f'SMTP connectivity test failed: {str(e)}')
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error testing Email service: {str(e)}")
            return {
                'service': 'Email',
                'status': 'error',
                'error': str(e),
                'recommendations': ['Fix Email service testing error: ' + str(e)]
            }
    
    def _analyze_sms_config(self) -> Dict[str, Any]:
        """Analyze SMS configuration details"""
        try:
            config_details = {
                'api_key': {
                    'configured': bool(current_app.config.get('SMS_API_KEY')),
                    'length': len(current_app.config.get('SMS_API_KEY', '')) if current_app.config.get('SMS_API_KEY') else 0
                },
                'api_secret': {
                    'configured': bool(current_app.config.get('SMS_API_SECRET')),
                    'length': len(current_app.config.get('SMS_API_SECRET', '')) if current_app.config.get('SMS_API_SECRET') else 0
                },
                'from_number': {
                    'configured': bool(current_app.config.get('SMS_FROM_NUMBER')),
                    'value': current_app.config.get('SMS_FROM_NUMBER', 'Not set')
                }
            }
            
            # Detect provider type
            api_key = current_app.config.get('SMS_API_KEY', '')
            if 'twilio' in api_key.lower():
                config_details['detected_provider'] = 'Twilio'
            elif 'nexmo' in api_key.lower():
                config_details['detected_provider'] = 'Nexmo/Vonage'
            else:
                config_details['detected_provider'] = 'Unknown/Custom'
            
            return config_details
            
        except Exception as e:
            return {'error': str(e)}
    
    def _analyze_email_config(self) -> Dict[str, Any]:
        """Analyze Email configuration details"""
        try:
            config_details = {
                'smtp_server': {
                    'configured': bool(current_app.config.get('MAIL_SERVER')),
                    'value': current_app.config.get('MAIL_SERVER', 'Not set')
                },
                'smtp_port': {
                    'configured': bool(current_app.config.get('MAIL_PORT')),
                    'value': current_app.config.get('MAIL_PORT', 'Not set')
                },
                'username': {
                    'configured': bool(current_app.config.get('MAIL_USERNAME')),
                    'value': self._mask_email(current_app.config.get('MAIL_USERNAME', 'Not set'))
                },
                'password': {
                    'configured': bool(current_app.config.get('MAIL_PASSWORD')),
                    'length': len(current_app.config.get('MAIL_PASSWORD', '')) if current_app.config.get('MAIL_PASSWORD') else 0
                },
                'use_tls': {
                    'value': current_app.config.get('MAIL_USE_TLS', False)
                },
                'use_ssl': {
                    'value': current_app.config.get('MAIL_USE_SSL', False)
                }
            }
            
            # Detect provider type
            server = current_app.config.get('MAIL_SERVER', '').lower()
            if 'gmail' in server:
                config_details['detected_provider'] = 'Gmail'
            elif 'outlook' in server or 'hotmail' in server:
                config_details['detected_provider'] = 'Outlook/Hotmail'
            elif 'yahoo' in server:
                config_details['detected_provider'] = 'Yahoo'
            else:
                config_details['detected_provider'] = 'Custom SMTP'
            
            return config_details
            
        except Exception as e:
            return {'error': str(e)}
    
    def _test_sms_connectivity(self, sms_service: SMSService) -> Dict[str, Any]:
        """Test SMS provider connectivity"""
        try:
            if sms_service.provider == 'twilio':
                return self._test_twilio_connectivity(sms_service)
            elif sms_service.provider == 'nexmo':
                return self._test_nexmo_connectivity(sms_service)
            else:
                return {'success': False, 'error': 'Unknown SMS provider'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _test_twilio_connectivity(self, sms_service: SMSService) -> Dict[str, Any]:
        """Test Twilio API connectivity"""
        try:
            account_sid = getattr(sms_service, 'api_key', None) or current_app.config.get('SMS_API_KEY')
            auth_token = getattr(sms_service, 'api_secret', None) or current_app.config.get('SMS_API_SECRET')
            
            if not account_sid or not auth_token:
                return {'success': False, 'provider': 'Twilio', 'error': 'Missing API credentials'}
            
            # Test Twilio API endpoint
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}.json"
            
            response = requests.get(url, auth=(account_sid, auth_token), timeout=10)
            
            if response.status_code == 200:
                account_info = response.json()
                return {
                    'success': True,
                    'provider': 'Twilio',
                    'account_status': account_info.get('status', 'unknown'),
                    'account_name': account_info.get('friendly_name', 'N/A')
                }
            else:
                return {
                    'success': False,
                    'provider': 'Twilio',
                    'error': f"HTTP {response.status_code}: {response.text[:200]}"
                }
                
        except Exception as e:
            return {'success': False, 'provider': 'Twilio', 'error': str(e)}
    
    def _test_nexmo_connectivity(self, sms_service: SMSService) -> Dict[str, Any]:
        """Test Nexmo/Vonage API connectivity"""
        try:
            api_key = getattr(sms_service, 'api_key', None) or current_app.config.get('SMS_API_KEY')
            api_secret = getattr(sms_service, 'api_secret', None) or current_app.config.get('SMS_API_SECRET')
            
            if not api_key or not api_secret:
                return {'success': False, 'provider': 'Nexmo/Vonage', 'error': 'Missing API credentials'}
            
            # Test Nexmo account balance endpoint
            url = "https://rest.nexmo.com/account/get-balance"
            
            params = {
                'api_key': api_key,
                'api_secret': api_secret
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                balance_info = response.json()
                return {
                    'success': True,
                    'provider': 'Nexmo/Vonage',
                    'balance': balance_info.get('value', 'N/A'),
                    'auto_reload': balance_info.get('autoReload', 'N/A')
                }
            else:
                return {
                    'success': False,
                    'provider': 'Nexmo/Vonage',
                    'error': f"HTTP {response.status_code}: {response.text[:200]}"
                }
                
        except Exception as e:
            return {'success': False, 'provider': 'Nexmo/Vonage', 'error': str(e)}
    
    def _test_smtp_connectivity(self) -> Dict[str, Any]:
        """Test SMTP server connectivity"""
        try:
            server = current_app.config.get('MAIL_SERVER')
            port = current_app.config.get('MAIL_PORT', 587)
            username = current_app.config.get('MAIL_USERNAME')
            password = current_app.config.get('MAIL_PASSWORD')
            use_tls = current_app.config.get('MAIL_USE_TLS', True)
            use_ssl = current_app.config.get('MAIL_USE_SSL', False)
            
            if use_ssl:
                smtp = smtplib.SMTP_SSL(server, port, timeout=10)
            else:
                smtp = smtplib.SMTP(server, port, timeout=10)
                smtp.ehlo()
                
                if use_tls:
                    smtp.starttls()
                    smtp.ehlo()
            
            smtp.login(username, password)
            smtp.quit()
            
            return {
                'success': True,
                'server': server,
                'port': port,
                'encryption': 'SSL' if use_ssl else 'TLS' if use_tls else 'None',
                'authentication': 'Success'
            }
            
        except smtplib.SMTPAuthenticationError as e:
            return {
                'success': False,
                'error': f"Authentication failed: {str(e)}",
                'error_type': 'authentication'
            }
        except smtplib.SMTPConnectError as e:
            return {
                'success': False,
                'error': f"Connection failed: {str(e)}",
                'error_type': 'connection'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': 'general'
            }
    
    def send_test_messages(self, test_email: Optional[str] = None, test_phone: Optional[str] = None) -> Dict[str, Any]:
        """
        Send test messages to verify functionality
        
        Args:
            test_email: Email address for test email
            test_phone: Phone number for test SMS
            
        Returns:
            dict: Test results
        """
        results = {
            'timestamp': datetime.now().isoformat(),
            'email': None,
            'sms': None
        }
        
        # Test email sending
        if test_email:
            try:
                email_service = EmailService()
                success = email_service.send_test_email('security', test_email)
                results['email'] = {
                    'success': success,
                    'recipient': self._mask_email(test_email),
                    'message': 'Test email sent successfully' if success else 'Test email failed'
                }
            except Exception as e:
                results['email'] = {
                    'success': False,
                    'recipient': self._mask_email(test_email),
                    'error': str(e)
                }
        
        # Test SMS sending
        if test_phone:
            try:
                sms_service = SMSService()
                test_message = f"[TEST] Phishing Simulator test SMS - {datetime.now().strftime('%H:%M')}"
                success = sms_service.send_test_sms(test_message, test_phone)
                results['sms'] = {
                    'success': success,
                    'recipient': self._mask_phone(test_phone),
                    'message': 'Test SMS sent successfully' if success else 'Test SMS failed'
                }
            except Exception as e:
                results['sms'] = {
                    'success': False,
                    'recipient': self._mask_phone(test_phone),
                    'error': str(e)
                }
        
        return results
    
    def _mask_email(self, email: str) -> str:
        """Mask email address for privacy"""
        if not email or '@' not in email:
            return email
        
        local, domain = email.split('@', 1)
        if len(local) <= 3:
            masked_local = local[0] + '*' * (len(local) - 1)
        else:
            masked_local = local[:2] + '*' * (len(local) - 4) + local[-2:]
        
        return f"{masked_local}@{domain}"
    
    def _mask_phone(self, phone: str) -> str:
        """Mask phone number for privacy"""
        if not phone:
            return phone
        
        # Remove non-digits for masking calculation
        digits_only = ''.join(filter(str.isdigit, phone))
        if len(digits_only) <= 4:
            return phone
        
        # Keep first 2 and last 2 digits, mask the middle
        return phone[:3] + '*' * (len(phone) - 6) + phone[-3:]
    
    def generate_config_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive configuration report
        
        Returns:
            dict: Configuration status report
        """
        try:
            report = {
                'timestamp': datetime.now().isoformat(),
                'environment': {
                    'flask_env': os.environ.get('FLASK_ENV', 'not set'),
                    'debug_mode': current_app.debug,
                    'config_source': 'environment variables'
                },
                'sms_config': self._analyze_sms_config(),
                'email_config': self._analyze_email_config(),
                'recommendations': []
            }
            
            # Add recommendations based on configuration
            if not report['sms_config'].get('api_key', {}).get('configured'):
                report['recommendations'].append('Configure SMS_API_KEY for SMS functionality')
            
            if not report['email_config'].get('smtp_server', {}).get('configured'):
                report['recommendations'].append('Configure MAIL_SERVER for email functionality')
            
            if current_app.debug:
                report['recommendations'].append('Disable debug mode in production')
            
            return report
            
        except Exception as e:
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'recommendations': ['Fix configuration report generation error']
            }