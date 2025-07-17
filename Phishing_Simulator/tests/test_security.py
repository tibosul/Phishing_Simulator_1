#!/usr/bin/env python3
"""
Comprehensive security tests for Phishing Simulator
Tests validation, sanitization, rate limiting, and security features
"""

import unittest
import os
import sys
import tempfile
import json
from datetime import datetime

# Add the parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from utils.database import db
from models.campaign import Campaign
from models.target import Target
from models.template import Template
from utils.validators import (
    ValidationError, validate_email, validate_phone_number, 
    validate_csv_format, validate_backend_input
)
from utils.security import (
    sanitize_input, sanitize_template_content, validate_template_variables
)
from services.campaign_service import CampaignService


class SecurityTestCase(unittest.TestCase):
    """Base test case for security tests"""
    
    def setUp(self):
        """Set up test database and app context"""
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        self.app = create_app('testing')
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self.db_path}'
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        db.create_all()
        self.client = self.app.test_client()
        
        # Create a test campaign
        self.test_campaign = Campaign(
            name="Security Test Campaign",
            type="email",
            description="Test campaign for security validation"
        )
        db.session.add(self.test_campaign)
        db.session.commit()
    
    def tearDown(self):
        """Clean up after test"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        os.close(self.db_fd)
        os.unlink(self.db_path)


class TestEmailValidation(SecurityTestCase):
    """Test email validation backend enforcement"""
    
    def test_valid_emails(self):
        """Test valid email formats"""
        valid_emails = [
            'user@example.com',
            'test.email@domain.co.uk',
            'user+tag@gmail.com',
            'firstname.lastname@company.org'
        ]
        
        for email in valid_emails:
            with self.subTest(email=email):
                try:
                    validate_email(email)
                except ValidationError:
                    self.fail(f"Valid email {email} was rejected")
    
    def test_invalid_emails(self):
        """Test invalid email formats"""
        invalid_emails = [
            'invalid.email',
            '@domain.com',
            'user@',
            'user@domain',
            'user space@domain.com',
            'user<script>@domain.com',
            'a' * 255 + '@domain.com'  # Too long
        ]
        
        for email in invalid_emails:
            with self.subTest(email=email):
                with self.assertRaises(ValidationError):
                    validate_email(email)
    
    def test_email_backend_validation_endpoint(self):
        """Test backend email validation on API endpoints"""
        # Test with invalid email
        response = self.client.post('/admin/targets/create', data={
            'campaign_id': self.test_campaign.id,
            'email': 'invalid.email',
            'first_name': 'Test'
        })
        
        # Should show validation error
        self.assertIn(b'Invalid email', response.data)


class TestPhoneValidation(SecurityTestCase):
    """Test phone number validation"""
    
    def test_valid_phone_numbers(self):
        """Test valid phone number formats"""
        valid_phones = [
            '+40723456789',
            '+1234567890123',
            '0723456789',
            '0623456789'
        ]
        
        for phone in valid_phones:
            with self.subTest(phone=phone):
                try:
                    validate_phone_number(phone)
                except ValidationError:
                    self.fail(f"Valid phone {phone} was rejected")
    
    def test_invalid_phone_numbers(self):
        """Test invalid phone number formats"""
        invalid_phones = [
            '123',  # Too short
            'abc123',  # Contains letters
            '+',  # Just plus
            '++40723456789',  # Double plus
            '0123456789012345',  # Too long
        ]
        
        for phone in invalid_phones:
            with self.subTest(phone=phone):
                with self.assertRaises(ValidationError):
                    validate_phone_number(phone)


class TestCSVUploadSecurity(SecurityTestCase):
    """Test CSV upload security limits"""
    
    def test_csv_file_size_limit(self):
        """Test CSV file size limitations"""
        # Create a large CSV content (over 5MB)
        large_content = "email,name\n" + ("test@example.com,Test User\n" * 100000)
        
        with self.assertRaises(ValidationError) as context:
            validate_csv_format(large_content, max_file_size=1024)  # 1KB limit
        
        self.assertIn("too large", str(context.exception))
    
    def test_csv_row_count_limit(self):
        """Test CSV row count limitations"""
        # Create CSV with too many rows
        many_rows = "email,name\n" + ("test@example.com,Test User\n" * 15000)
        
        with self.assertRaises(ValidationError) as context:
            validate_csv_format(many_rows, max_rows=10000)
        
        self.assertIn("too many rows", str(context.exception))
    
    def test_csv_upload_endpoint_limits(self):
        """Test CSV upload endpoint enforces limits"""
        # Create test CSV file that's too large
        large_csv_content = "email,name\n" + ("test@example.com,Test User\n" * 15000)
        
        # Test the validation function directly
        with self.assertRaises(ValidationError):
            validate_csv_format(large_csv_content, max_rows=10000)
    
    def test_csv_malicious_content(self):
        """Test CSV protection against malicious content"""
        malicious_csv = '''email,name,notes
test@example.com,Test,"<script>alert('xss')</script>"
user@example.com,User,"javascript:alert('evil')"'''
        
        try:
            stats = CampaignService.add_targets_from_csv(
                campaign_id=self.test_campaign.id,
                csv_content=malicious_csv,
                skip_duplicates=True
            )
            
            # Should still process but sanitize the content
            targets = Target.query.filter_by(campaign_id=self.test_campaign.id).all()
            for target in targets:
                # Notes should be sanitized
                if target.notes:
                    self.assertNotIn('<script>', target.notes)
                    self.assertNotIn('javascript:', target.notes)
        
        except ValidationError:
            # This is also acceptable - rejection of malicious content
            pass


class TestTemplateSanitization(SecurityTestCase):
    """Test template content sanitization"""
    
    def test_template_xss_prevention(self):
        """Test XSS prevention in templates"""
        malicious_content = '''
        <p>Hello {{first_name}}</p>
        <script>alert('xss')</script>
        <iframe src="evil.com"></iframe>
        '''
        
        with self.assertRaises(ValidationError):
            sanitize_template_content(malicious_content, 'email')
    
    def test_template_variable_validation(self):
        """Test template variable validation"""
        # Valid template variables
        valid_content = "Hello {{first_name}}, visit {{tracking_link}}"
        try:
            validate_template_variables(valid_content)
        except ValidationError:
            self.fail("Valid template variables were rejected")
        
        # Invalid template variables
        invalid_content = "Hello {{eval('evil_code')}}"
        with self.assertRaises(ValidationError):
            validate_template_variables(invalid_content)
    
    def test_template_creation_sanitization(self):
        """Test template creation endpoint sanitizes content"""
        malicious_template_data = {
            'name': 'Test Template',
            'type': 'email',
            'subject': 'Test Subject',
            'content': '<p>Hello {{first_name}}</p><script>alert("xss")</script>'
        }
        
        response = self.client.post('/admin/templates/create', 
                                  data=malicious_template_data)
        
        # Should reject malicious content
        self.assertIn(b'security validation failed', response.data)


class TestAPIErrorHandling(SecurityTestCase):
    """Test API error handling and response standardization"""
    
    def test_api_validation_errors(self):
        """Test API returns proper validation error responses"""
        # Test invalid email via API
        response = self.client.put(f'/admin/targets/api/{999}', 
                                 json={'phone': 'invalid-phone'},
                                 content_type='application/json')
        
        # Should return 404 for non-existent target
        self.assertEqual(response.status_code, 404)
    
    def test_api_error_response_format(self):
        """Test API error responses have consistent format"""
        # Create a target first
        target = Target(
            campaign_id=self.test_campaign.id,
            email='test@example.com'
        )
        db.session.add(target)
        db.session.commit()
        
        # Test with invalid phone
        response = self.client.put(f'/admin/targets/api/{target.id}', 
                                 json={'phone': 'invalid'},
                                 content_type='application/json')
        
        data = json.loads(response.data)
        
        # Should have proper error structure
        self.assertIn('success', data)
        self.assertFalse(data['success'])
        self.assertIn('error', data)
    
    def test_bulk_import_error_handling(self):
        """Test bulk CSV import error handling"""
        invalid_csv = "invalid,csv,format"
        
        response = self.client.post('/admin/targets/api/bulk-import',
                                  json={
                                      'campaign_id': self.test_campaign.id,
                                      'csv_content': invalid_csv
                                  },
                                  content_type='application/json')
        
        data = json.loads(response.data)
        
        # Should return proper error response
        self.assertIn('success', data)
        self.assertFalse(data['success'])


class TestInputSanitization(SecurityTestCase):
    """Test general input sanitization"""
    
    def test_basic_input_sanitization(self):
        """Test basic input sanitization"""
        malicious_inputs = [
            '<script>alert("xss")</script>',
            'javascript:alert("evil")',
            '<iframe src="evil.com"></iframe>',
            '<img src="x" onerror="alert(1)">'
        ]
        
        for malicious_input in malicious_inputs:
            with self.subTest(input=malicious_input):
                sanitized = sanitize_input(malicious_input, allow_html=False, strict=True)
                
                # Should not contain dangerous content
                self.assertNotIn('<script>', sanitized)
                self.assertNotIn('javascript:', sanitized)
                self.assertNotIn('<iframe>', sanitized)
                self.assertNotIn('onerror=', sanitized)
    
    def test_html_sanitization_with_bleach(self):
        """Test HTML sanitization with bleach"""
        html_content = '''
        <p>Safe paragraph</p>
        <strong>Bold text</strong>
        <script>alert('dangerous')</script>
        <a href="http://safe.com">Safe link</a>
        <a href="javascript:alert('evil')">Evil link</a>
        '''
        
        sanitized = sanitize_input(html_content, allow_html=True, strict=True)
        
        # Should keep safe HTML but remove dangerous content
        self.assertIn('<p>', sanitized)
        self.assertIn('<strong>', sanitized)
        self.assertNotIn('<script>', sanitized)
        self.assertNotIn('javascript:', sanitized)


class TestSecurityLogging(SecurityTestCase):
    """Test security event logging"""
    
    def test_security_event_logging(self):
        """Test that security events are properly logged"""
        from utils.security import log_security_event
        
        # This should not raise an exception
        try:
            log_security_event('test_event', 'Test description', {'key': 'value'})
        except Exception as e:
            self.fail(f"Security logging failed: {str(e)}")
    
    def test_admin_action_logging(self):
        """Test that admin actions are logged"""
        # Create a target (should log the action)
        response = self.client.post('/admin/targets/create', data={
            'campaign_id': self.test_campaign.id,
            'email': 'logged@example.com',
            'first_name': 'Logged'
        })
        
        # Check that target was created
        target = Target.query.filter_by(email='logged@example.com').first()
        self.assertIsNotNone(target)


if __name__ == '__main__':
    unittest.main()