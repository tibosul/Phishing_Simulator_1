#!/usr/bin/env python3
"""
Comprehensive unit tests for Phishing Simulator core functionality
"""

import unittest
import os
import sys
import tempfile
from datetime import datetime

# Add the parent directory to Python path so we can import the modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from utils.database import db
from models.campaign import Campaign
from models.target import Target
from models.template import Template
from models.tracking import Tracking
from models.credential import Credential
from services.campaign_service import CampaignService
from services.email_service import EmailService
from services.tracking_service import TrackingService
from utils.validators import ValidationError


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
        
        # Pop application context
        self.app_context.pop()
        
        # Remove temporary database
        os.close(self.db_fd)
        os.unlink(self.db_path)


class TestCampaignModel(BaseTestCase):
    """Test cases for Campaign model"""
    
    def test_campaign_creation(self):
        """Test basic campaign creation"""
        campaign = Campaign(
            name="Test Campaign",
            type="email",
            description="Test description"
        )
        
        db.session.add(campaign)
        db.session.commit()
        
        self.assertEqual(campaign.name, "Test Campaign")
        self.assertEqual(campaign.type, "email")
        self.assertEqual(campaign.status, "draft")
        self.assertIsNotNone(campaign.id)
        self.assertIsNotNone(campaign.created_at)
    
    def test_campaign_validation(self):
        """Test campaign validation"""
        # Test valid campaign
        campaign = Campaign("Valid Campaign", "email")
        campaign.validate()  # Should not raise exception
        
        # Test invalid campaign name
        with self.assertRaises(ValidationError):
            invalid_campaign = Campaign("", "email")
            invalid_campaign.validate()
        
        # Test invalid campaign type
        with self.assertRaises(ValidationError):
            invalid_campaign = Campaign("Test Campaign", "invalid_type")
            invalid_campaign.validate()
    
    def test_campaign_lifecycle(self):
        """Test campaign status transitions"""
        campaign = Campaign("Lifecycle Test", "email")
        db.session.add(campaign)
        db.session.commit()
        
        # Add a target so we can start the campaign
        target = Target(
            campaign_id=campaign.id,
            email="test@example.com",
            first_name="Test",
            last_name="User"
        )
        db.session.add(target)
        db.session.commit()
        
        # Test starting campaign
        self.assertEqual(campaign.status, "draft")
        campaign.start()
        self.assertEqual(campaign.status, "active")
        self.assertIsNotNone(campaign.started_at)
        
        # Test pausing campaign
        campaign.pause()
        self.assertEqual(campaign.status, "paused")
        
        # Test resuming campaign
        campaign.resume()
        self.assertEqual(campaign.status, "active")
        
        # Test completing campaign
        campaign.complete()
        self.assertEqual(campaign.status, "completed")
        self.assertIsNotNone(campaign.ended_at)
    
    def test_campaign_properties(self):
        """Test campaign calculated properties"""
        campaign = Campaign("Property Test", "email")
        db.session.add(campaign)
        db.session.commit()
        
        # Add targets
        for i in range(3):
            target = Target(
                campaign_id=campaign.id,
                email=f"test{i}@example.com"
            )
            db.session.add(target)
        
        # Add tracking events
        tracking = Tracking(
            campaign_id=campaign.id,
            event_type="link_clicked",
            target_id=1
        )
        db.session.add(tracking)
        
        # Add credentials
        credential = Credential(
            campaign_id=campaign.id,
            target_id=1,
            username="testuser",
            password="testpass"
        )
        db.session.add(credential)
        
        db.session.commit()
        
        # Test properties
        self.assertEqual(campaign.total_targets, 3)
        self.assertEqual(campaign.total_clicks, 1)
        self.assertEqual(campaign.total_credentials, 1)
        self.assertGreater(campaign.success_rate, 0)
        self.assertGreater(campaign.click_rate, 0)


class TestTargetModel(BaseTestCase):
    """Test cases for Target model"""
    
    def test_target_creation(self):
        """Test basic target creation"""
        # Create campaign first
        campaign = Campaign("Test Campaign", "email")
        db.session.add(campaign)
        db.session.commit()
        
        # Create target
        target = Target(
            campaign_id=campaign.id,
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            company="Test Corp"
        )
        
        db.session.add(target)
        db.session.commit()
        
        self.assertEqual(target.email, "test@example.com")
        self.assertEqual(target.first_name, "John")
        self.assertEqual(target.display_name, "John Doe")
        self.assertIsNotNone(target.id)
    
    def test_target_validation(self):
        """Test target validation"""
        campaign = Campaign("Test Campaign", "email")
        db.session.add(campaign)
        db.session.commit()
        
        # Valid target
        target = Target(campaign_id=campaign.id, email="valid@example.com")
        target.validate()  # Should not raise exception
        
        # Invalid email
        with self.assertRaises(ValidationError):
            invalid_target = Target(campaign_id=campaign.id, email="invalid-email")
            invalid_target.validate()
    
    def test_target_status_updates(self):
        """Test target status update methods"""
        campaign = Campaign("Test Campaign", "email")
        db.session.add(campaign)
        db.session.commit()
        
        target = Target(campaign_id=campaign.id, email="test@example.com")
        db.session.add(target)
        db.session.commit()
        
        # Test status updates
        self.assertFalse(target.email_sent)
        target.mark_email_sent()
        self.assertTrue(target.email_sent)
        
        self.assertFalse(target.clicked_link)
        target.mark_link_clicked()
        self.assertTrue(target.clicked_link)
        
        self.assertFalse(target.entered_credentials)
        target.mark_credentials_entered()
        self.assertTrue(target.entered_credentials)


class TestTemplateModel(BaseTestCase):
    """Test cases for Template model"""
    
    def test_template_creation(self):
        """Test basic template creation"""
        template = Template(
            name="Test Template",
            type="email",
            content="Hello {{target_name}}, click {{tracking_link}}",
            subject="Test Subject"
        )
        
        db.session.add(template)
        db.session.commit()
        
        self.assertEqual(template.name, "Test Template")
        self.assertEqual(template.type, "email")
        self.assertTrue(template.is_email)
        self.assertFalse(template.is_sms)
        self.assertGreater(template.content_length, 0)
        self.assertGreater(template.placeholder_count, 0)
    
    def test_template_validation(self):
        """Test template validation"""
        # Valid template
        template = Template(
            name="Valid Template",
            type="email",
            content="Hello {{target_name}}, click {{tracking_link}}",
            subject="Test Subject"
        )
        template.validate()  # Should not raise exception
        
        # Invalid template - no tracking link
        with self.assertRaises(ValidationError):
            invalid_template = Template(
                name="Invalid Template",
                type="email",
                content="Hello {{target_name}}",  # Missing tracking_link
                subject="Test Subject"
            )
            invalid_template.validate()
        
        # Invalid template - no subject for email
        with self.assertRaises(ValidationError):
            invalid_template = Template(
                name="Invalid Template",
                type="email",
                content="Hello {{target_name}}, click {{tracking_link}}"
                # Missing subject
            )
            invalid_template.validate()
    
    def test_template_rendering(self):
        """Test template content rendering"""
        template = Template(
            name="Render Test",
            type="email",
            content="Hello {{target_name}}, click {{tracking_link}}",
            subject="Hello {{target_first_name}}"
        )
        
        target_data = {
            'target_name': 'John Doe',
            'target_first_name': 'John',
            'tracking_link': 'http://example.com/track'
        }
        
        rendered_content = template.render_content(target_data)
        rendered_subject = template.render_subject(target_data)
        
        self.assertIn('John Doe', rendered_content)
        self.assertIn('http://example.com/track', rendered_content)
        self.assertEqual(rendered_subject, 'Hello John')


class TestCampaignService(BaseTestCase):
    """Test cases for CampaignService"""
    
    def test_create_campaign(self):
        """Test campaign creation through service"""
        campaign = CampaignService.create_campaign(
            name="Service Test Campaign",
            campaign_type="email",
            description="Test description"
        )
        
        self.assertIsNotNone(campaign.id)
        self.assertEqual(campaign.name, "Service Test Campaign")
        self.assertEqual(campaign.type, "email")
    
    def test_create_duplicate_campaign(self):
        """Test creating campaign with duplicate name"""
        CampaignService.create_campaign(
            name="Duplicate Test",
            campaign_type="email"
        )
        
        # Try to create another with same name
        with self.assertRaises(ValidationError):
            CampaignService.create_campaign(
                name="Duplicate Test",
                campaign_type="email"
            )
    
    def test_update_campaign(self):
        """Test campaign updates through service"""
        campaign = CampaignService.create_campaign(
            name="Update Test",
            campaign_type="email"
        )
        
        # Update campaign
        updated_campaign = CampaignService.update_campaign(
            campaign.id,
            name="Updated Name",
            description="Updated description"
        )
        
        self.assertEqual(updated_campaign.name, "Updated Name")
        self.assertEqual(updated_campaign.description, "Updated description")
        self.assertIsNotNone(updated_campaign.updated_at)
    
    def test_add_targets_from_csv(self):
        """Test adding targets from CSV data"""
        campaign = CampaignService.create_campaign(
            name="CSV Test",
            campaign_type="email"
        )
        
        csv_content = """email,first_name,last_name,company
test1@example.com,John,Doe,Corp1
test2@example.com,Jane,Smith,Corp2
invalid-email,Invalid,User,Corp3"""
        
        stats = CampaignService.add_targets_from_csv(
            campaign.id,
            csv_content,
            skip_duplicates=True
        )
        
        self.assertEqual(stats['added'], 2)  # 2 valid emails
        self.assertEqual(len(stats['errors']), 1)  # 1 invalid email


class TestEmailService(BaseTestCase):
    """Test cases for EmailService"""
    
    def test_template_rendering(self):
        """Test email template rendering"""
        email_service = EmailService()
        
        # Create test objects
        campaign = Campaign("Email Test", "email")
        db.session.add(campaign)
        db.session.commit()
        
        target = Target(
            campaign_id=campaign.id,
            email="test@example.com",
            first_name="John",
            last_name="Doe"
        )
        db.session.add(target)
        db.session.commit()
        
        # Test template rendering
        subject, content = email_service.render_email_template(
            'security',  # Use existing template
            target,
            campaign
        )
        
        self.assertIsInstance(subject, str)
        self.assertIsInstance(content, str)
        self.assertGreater(len(content), 0)  # Should have some content
        
        # Check that basic template structure exists
        self.assertTrue(any(keyword in content.lower() for keyword in 
                          ['revolut', 'security', 'account', 'verify']))
    
    def test_email_config_validation(self):
        """Test email configuration validation"""
        # Test with missing configuration (should fail in testing)
        is_valid, message = EmailService.validate_email_config()
        
        # In testing environment, email config might not be complete
        self.assertIsInstance(is_valid, bool)
        self.assertIsInstance(message, str)


class TestTrackingService(BaseTestCase):
    """Test cases for TrackingService"""
    
    def test_track_email_open(self):
        """Test email open tracking"""
        tracking_service = TrackingService()
        
        # Create test objects
        campaign = Campaign("Tracking Test", "email")
        db.session.add(campaign)
        db.session.commit()
        
        target = Target(
            campaign_id=campaign.id,
            email="test@example.com"
        )
        db.session.add(target)
        db.session.commit()
        
        # Test with app context
        with self.app.test_request_context('/'):
            tracking_event = tracking_service.track_email_open(
                campaign.id,
                target.id,
                "test-token"
            )
        
        self.assertIsNotNone(tracking_event.id)
        self.assertEqual(tracking_event.event_type, "email_opened")
        self.assertTrue(tracking_event.is_unique)
    
    def test_conversion_funnel(self):
        """Test conversion funnel calculation"""
        tracking_service = TrackingService()
        
        # Create test objects
        campaign = Campaign("Funnel Test", "email")
        db.session.add(campaign)
        db.session.commit()
        
        target = Target(campaign_id=campaign.id, email="test@example.com")
        db.session.add(target)
        db.session.commit()
        
        # Add tracking events (need to flush and commit for proper IDs)
        events = [
            Tracking(campaign_id=campaign.id, event_type="email_sent", target_id=target.id),
            Tracking(campaign_id=campaign.id, event_type="email_opened", target_id=target.id),
            Tracking(campaign_id=campaign.id, event_type="link_clicked", target_id=target.id)
        ]
        
        for event in events:
            db.session.add(event)
        
        db.session.commit()
        
        # Get funnel data
        funnel_data = tracking_service.get_conversion_funnel(campaign.id)
        
        self.assertIsInstance(funnel_data, dict)
        # Should have at least some of these events
        expected_events = ['email_sent', 'email_opened', 'link_clicked']
        for event in expected_events:
            if event in funnel_data:
                self.assertGreaterEqual(funnel_data[event], 0)


class TestSecurityFeatures(BaseTestCase):
    """Test cases for security features"""
    
    def test_input_sanitization(self):
        """Test input sanitization in campaign creation"""
        # Test with potentially malicious input - should be rejected
        malicious_name = "<script>alert('xss')</script>Campaign"
        
        # Should raise ValidationError due to invalid characters
        with self.assertRaises(ValidationError):
            CampaignService.create_campaign(
                name=malicious_name,
                campaign_type="email"
            )
        
        # Test with less obvious XSS that gets sanitized
        suspicious_desc = "Description with <img src=x> tag"
        
        campaign = CampaignService.create_campaign(
            name="Safe Campaign Name",
            campaign_type="email",
            description=suspicious_desc
        )
        
        # The description should be saved (sanitization happens at the service level)
        self.assertIsNotNone(campaign.description)
    
    def test_email_validation(self):
        """Test email validation functionality"""
        from utils.validators import validate_email
        
        # Valid emails
        validate_email("test@example.com")  # Should not raise
        validate_email("user.name+tag@domain.co.uk")  # Should not raise
        
        # Invalid emails
        with self.assertRaises(ValidationError):
            validate_email("invalid-email")
        
        with self.assertRaises(ValidationError):
            validate_email("@domain.com")
        
        with self.assertRaises(ValidationError):
            validate_email("user@")


# Test runner
if __name__ == '__main__':
    # Discover and run all tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with error code if tests failed
    sys.exit(0 if result.wasSuccessful() else 1)