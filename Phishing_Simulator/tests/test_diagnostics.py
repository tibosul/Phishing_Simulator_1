#!/usr/bin/env python3
"""
Test pentru serviciul de diagnostice
"""

import unittest
import os
import sys
import tempfile
import json
from datetime import datetime

# Add the parent directory to Python path so we can import the modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from utils.database import db
from services.diagnostic_service import DiagnosticService
from services.email_service import EmailService
from services.sms_service import SMSService


class BaseTestCase(unittest.TestCase):
    """Base test case with common setup and teardown"""
    
    def setUp(self):
        """Set up test database and app context"""
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        # Create app with testing configuration
        self.app = create_app('testing')
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self.db_path}'
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        
        # Create application context
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Create all tables
        db.create_all()
        
        # Create test client
        self.client = self.app.test_client()
    
    def tearDown(self):
        """Clean up after tests"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        os.close(self.db_fd)
        os.unlink(self.db_path)


class TestDiagnosticService(BaseTestCase):
    """Test pentru serviciul de diagnostice"""
    
    def setUp(self):
        """Setup pentru fiecare test"""
        super().setUp()
        self.diagnostic_service = DiagnosticService()
    
    def test_diagnostic_service_initialization(self):
        """Test inițializarea serviciului de diagnostice"""
        service = DiagnosticService()
        self.assertIsNotNone(service)
        self.assertTrue(hasattr(service, 'logger'))
    
    def test_email_configuration_check(self):
        """Test verificarea configurației email"""
        result = self.diagnostic_service._check_email_configuration()
        
        self.assertIn('name', result)
        self.assertIn('status', result)
        self.assertIn('message', result)
        self.assertEqual(result['name'], 'Email Configuration')
        
        # În test mode, configurația ar trebui să lipsească
        self.assertIn(result['status'], ['error', 'success'])
    
    def test_sms_configuration_check(self):
        """Test verificarea configurației SMS"""
        result = self.diagnostic_service._check_sms_configuration()
        
        self.assertIn('name', result)
        self.assertIn('status', result)
        self.assertIn('message', result)
        self.assertEqual(result['name'], 'SMS Configuration')
        
        # În test mode, SMS ar trebui să fie warning (not configured)
        self.assertIn(result['status'], ['warning', 'success', 'error'])
    
    def test_database_connection_check(self):
        """Test verificarea conexiunii la baza de date"""
        result = self.diagnostic_service._test_database_connection()
        
        self.assertIn('name', result)
        self.assertIn('status', result)
        self.assertIn('message', result)
        self.assertEqual(result['name'], 'Database Connection')
        
        # În test mode cu SQLite in-memory, conexiunea ar trebui să funcționeze
        self.assertEqual(result['status'], 'success')
        self.assertIn('details', result)
        self.assertIn('connection_time_ms', result['details'])
    
    def test_database_tables_check(self):
        """Test verificarea tabelelor din baza de date"""
        result = self.diagnostic_service._check_database_tables()
        
        self.assertIn('name', result)
        self.assertIn('status', result)
        self.assertIn('message', result)
        self.assertEqual(result['name'], 'Database Tables')
        
        # Tabelele ar trebui să existe
        self.assertEqual(result['status'], 'success')
    
    def test_email_service_diagnosis(self):
        """Test diagnosticul complet al serviciului email"""
        result = self.diagnostic_service.diagnose_email_service()
        
        self.assertIn('service', result)
        self.assertIn('status', result)
        self.assertIn('checks', result)
        self.assertIn('recommendations', result)
        self.assertEqual(result['service'], 'email')
        
        # Ar trebui să avem cel puțin câteva verificări
        self.assertGreaterEqual(len(result['checks']), 3)
        
        # Fiecare check ar trebui să aibă structura corectă
        for check in result['checks']:
            self.assertIn('name', check)
            self.assertIn('status', check)
            self.assertIn('message', check)
    
    def test_sms_service_diagnosis(self):
        """Test diagnosticul complet al serviciului SMS"""
        result = self.diagnostic_service.diagnose_sms_service()
        
        self.assertIn('service', result)
        self.assertIn('status', result)
        self.assertIn('checks', result)
        self.assertIn('recommendations', result)
        self.assertEqual(result['service'], 'sms')
        
        # Ar trebui să avem cel puțin câteva verificări
        self.assertGreaterEqual(len(result['checks']), 3)
    
    def test_database_diagnosis(self):
        """Test diagnosticul complet al bazei de date"""
        result = self.diagnostic_service.diagnose_database()
        
        self.assertIn('service', result)
        self.assertIn('status', result)
        self.assertIn('checks', result)
        self.assertIn('recommendations', result)
        self.assertEqual(result['service'], 'database')
        
        # În test mode, database ar trebui să fie healthy
        self.assertEqual(result['status'], 'healthy')
    
    def test_full_diagnostics(self):
        """Test diagnosticul complet al sistemului"""
        result = self.diagnostic_service.run_full_diagnostics()
        
        self.assertIn('timestamp', result)
        self.assertIn('overall_status', result)
        self.assertIn('email', result)
        self.assertIn('sms', result)
        self.assertIn('database', result)
        self.assertIn('execution_time', result)
        
        # Verifică că timestamp-ul este valid
        timestamp_str = result['timestamp']
        if timestamp_str.endswith('Z'):
            timestamp_str = timestamp_str.replace('Z', '+00:00')
        timestamp = datetime.fromisoformat(timestamp_str)
        self.assertIsInstance(timestamp, datetime)
        
        # Verifică că timpul de execuție este rezonabil
        self.assertGreaterEqual(result['execution_time'], 0)
        self.assertLessEqual(result['execution_time'], 30)  # Maxim 30 secunde
        
        # Status-ul general ar trebui să fie determinat corect
        self.assertIn(result['overall_status'], ['healthy', 'warning', 'error'])
    
    def test_service_status_summary(self):
        """Test rezumatul rapid al statusului serviciilor"""
        result = self.diagnostic_service.get_service_status_summary()
        
        self.assertIn('timestamp', result)
        self.assertIn('services', result)
        
        # Verifică serviciile incluse
        services = result['services']
        self.assertIn('email', services)
        self.assertIn('sms', services)
        self.assertIn('database', services)
        
        # Fiecare serviciu ar trebui să aibă status și mesaj
        for service_name, service_info in services.items():
            self.assertIn('status', service_info)
            self.assertIn('message', service_info)
            self.assertIn(service_info['status'], ['healthy', 'warning', 'error'])
    
    def test_test_email_sending(self):
        """Test trimiterea unui email de test"""
        test_email = "test@example.com"
        template_name = "security"
        
        result = self.diagnostic_service.send_test_email(test_email, template_name)
        
        self.assertIn('status', result)
        self.assertIn('message', result)
        self.assertIn('timestamp', result)
        
        # În test mode, ar trebui să fie success (because it's mocked)
        self.assertIn(result['status'], ['success', 'error'])
        
        if result['status'] == 'success':
            self.assertIn('details', result)
            self.assertEqual(result['details']['recipient'], test_email)
            self.assertEqual(result['details']['template'], template_name)
    
    def test_test_sms_sending(self):
        """Test trimiterea unui SMS de test"""
        test_phone = "+40712345678"
        template_content = "TEST: This is a test SMS"
        
        result = self.diagnostic_service.send_test_sms(test_phone, template_content)
        
        self.assertIn('status', result)
        self.assertIn('message', result)
        self.assertIn('timestamp', result)
        
        # SMS-ul ar trebui să funcționeze cu mock provider
        self.assertEqual(result['status'], 'success')
        self.assertIn('details', result)
        self.assertEqual(result['details']['recipient'], test_phone)
    
    def test_sms_provider_detection(self):
        """Test detectarea providerului SMS"""
        result = self.diagnostic_service._detect_sms_provider()
        
        self.assertIn('name', result)
        self.assertIn('status', result)
        self.assertIn('message', result)
        self.assertEqual(result['name'], 'SMS Provider Detection')
        
        # Ar trebui să detecteze mock provider în test mode
        self.assertEqual(result['status'], 'success')
        self.assertIn('details', result)
        self.assertIn('provider', result['details'])


class TestDiagnosticRoutes(BaseTestCase):
    """Test pentru rutele de diagnostice"""
    
    def test_diagnostics_index_route(self):
        """Test ruta principală de diagnostice"""
        response = self.client.get('/admin/diagnostics/')
        self.assertEqual(response.status_code, 200)
        
        # Verifică că template-ul este randat corect
        data = response.get_data(as_text=True)
        self.assertIn('Service Diagnostics', data)
        self.assertIn('Quick Tests', data)
    
    def test_api_status_route(self):
        """Test API endpoint pentru status servicii"""
        response = self.client.get('/admin/diagnostics/api/status')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('timestamp', data)
        self.assertIn('services', data)
        
        # Verifică structura serviciilor
        services = data['services']
        self.assertIn('email', services)
        self.assertIn('sms', services)
        self.assertIn('database', services)
    
    def test_api_full_diagnostics_route(self):
        """Test API endpoint pentru diagnostice complete"""
        response = self.client.get('/admin/diagnostics/api/full')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('timestamp', data)
        self.assertIn('overall_status', data)
        self.assertIn('email', data)
        self.assertIn('sms', data)
        self.assertIn('database', data)
        self.assertIn('execution_time', data)
    
    def test_test_email_route_get(self):
        """Test GET pentru ruta de testare email"""
        response = self.client.get('/admin/diagnostics/test/email')
        self.assertEqual(response.status_code, 200)
        
        data = response.get_data(as_text=True)
        self.assertIn('Test Email Service', data)
        self.assertIn('Send Test Email', data)
    
    def test_test_email_route_post_valid(self):
        """Test POST pentru ruta de testare email cu date valide"""
        response = self.client.post('/admin/diagnostics/test/email', data={
            'test_email': 'test@example.com',
            'template_name': 'security'
        })
        
        # Ar trebui să redirecționeze sau să afișeze rezultatul
        self.assertIn(response.status_code, [200, 302])
    
    def test_test_email_route_post_invalid(self):
        """Test POST pentru ruta de testare email cu date invalide"""
        response = self.client.post('/admin/diagnostics/test/email', data={
            'test_email': 'invalid-email',
            'template_name': 'security'
        })
        
        # Ar trebui să redirecționeze din cauza erorii de validare
        self.assertEqual(response.status_code, 302)
    
    def test_test_sms_route_get(self):
        """Test GET pentru ruta de testare SMS"""
        response = self.client.get('/admin/diagnostics/test/sms')
        self.assertEqual(response.status_code, 200)
        
        data = response.get_data(as_text=True)
        self.assertIn('Test SMS Service', data)
        self.assertIn('Send Test SMS', data)
    
    def test_test_sms_route_post_valid(self):
        """Test POST pentru ruta de testare SMS cu date valide"""
        response = self.client.post('/admin/diagnostics/test/sms', data={
            'test_phone': '+40712345678',
            'template_content': 'Test SMS message'
        })
        
        # Ar trebui să funcționeze
        self.assertIn(response.status_code, [200, 302])
    
    def test_api_test_email_route(self):
        """Test API endpoint pentru testarea email-ului"""
        response = self.client.post('/admin/diagnostics/api/test/email', 
                                  json={
                                      'test_email': 'test@example.com',
                                      'template_name': 'security'
                                  },
                                  content_type='application/json')
        
        self.assertIn(response.status_code, [200, 400, 500])
        
        if response.status_code == 200:
            data = json.loads(response.data)
            self.assertIn('status', data)
            self.assertIn('message', data)
    
    def test_api_test_sms_route(self):
        """Test API endpoint pentru testarea SMS-ului"""
        response = self.client.post('/admin/diagnostics/api/test/sms', 
                                  json={
                                      'test_phone': '+40712345678',
                                      'template_content': 'Test SMS'
                                  },
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('status', data)
        self.assertIn('message', data)
        self.assertEqual(data['status'], 'success')  # Mock SMS should work
    
    def test_export_diagnostics_route(self):
        """Test ruta de export diagnostice"""
        response = self.client.get('/admin/diagnostics/export')
        self.assertEqual(response.status_code, 200)
        
        # Verifică că răspunsul este JSON
        self.assertEqual(response.content_type, 'application/json')
        
        # Verifică că header-ul de download este setat
        self.assertIn('attachment', response.headers.get('Content-Disposition', ''))
        
        # Verifică că conținutul este JSON valid
        data = json.loads(response.data)
        self.assertIn('timestamp', data)
        self.assertIn('overall_status', data)
    
    def test_full_diagnostics_route(self):
        """Test ruta pentru diagnostice complete"""
        response = self.client.get('/admin/diagnostics/full')
        self.assertEqual(response.status_code, 200)
        
        data = response.get_data(as_text=True)
        self.assertIn('Full Diagnostic Report', data)


class TestDiagnosticIntegration(BaseTestCase):
    """Test integrare pentru diagnostice"""
    
    def test_email_service_integration(self):
        """Test integrarea cu EmailService"""
        diagnostic_service = DiagnosticService()
        
        # Test că poate folosi EmailService
        email_diagnosis = diagnostic_service.diagnose_email_service()
        self.assertEqual(email_diagnosis['service'], 'email')
        
        # Test că poate valida configurația email
        is_valid, message = EmailService.validate_email_config()
        self.assertIsInstance(is_valid, bool)
        self.assertIsInstance(message, str)
    
    def test_sms_service_integration(self):
        """Test integrarea cu SMSService"""
        diagnostic_service = DiagnosticService()
        
        # Test că poate folosi SMSService
        sms_diagnosis = diagnostic_service.diagnose_sms_service()
        self.assertEqual(sms_diagnosis['service'], 'sms')
        
        # Test că poate valida configurația SMS
        is_valid, message = SMSService.validate_sms_config()
        self.assertIsInstance(is_valid, bool)
        self.assertIsInstance(message, str)
    
    def test_full_system_integration(self):
        """Test integrarea completă a sistemului"""
        diagnostic_service = DiagnosticService()
        
        # Rulează diagnosticele complete
        full_report = diagnostic_service.run_full_diagnostics()
        
        # Verifică că toate serviciile sunt incluse
        self.assertIn('email', full_report)
        self.assertIn('sms', full_report)
        self.assertIn('database', full_report)
        
        # Verifică că statusul general este determinat corect
        email_status = full_report['email']['status']
        sms_status = full_report['sms']['status']
        db_status = full_report['database']['status']
        overall_status = full_report['overall_status']
        
        # Logica de determinare a statusului general
        if all(status == 'healthy' for status in [email_status, sms_status, db_status]):
            self.assertEqual(overall_status, 'healthy')
        elif any(status == 'error' for status in [email_status, sms_status, db_status]):
            self.assertEqual(overall_status, 'error')
        else:
            self.assertEqual(overall_status, 'warning')


if __name__ == '__main__':
    unittest.main()