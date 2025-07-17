#!/usr/bin/env python3
"""
Integration tests for Phishing Simulator workflow
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
from models.tracking import Tracking
from models.credential import Credential
from services.campaign_service import CampaignService
from services.email_service import EmailService
from services.tracking_service import TrackingService
from utils.validators import ValidationError


class IntegrationTestCase(unittest.TestCase):
    """Base integration test case"""
    
    def setUp(self):
        """Set up test environment"""
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        self.app = create_app('testing')
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self.db_path}'
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        
        # Mock email configuration for testing
        self.app.config['MAIL_SERVER'] = 'smtp.gmail.com'
        self.app.config['MAIL_PORT'] = 587
        self.app.config['MAIL_USE_TLS'] = True
        self.app.config['MAIL_USERNAME'] = 'test@example.com'
        self.app.config['MAIL_PASSWORD'] = 'test_password'
        self.app.config['MAIL_DEFAULT_SENDER'] = 'test@example.com'
        self.app.config['BASE_URL'] = 'http://localhost:5000'
        
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        db.create_all()
        self.client = self.app.test_client()
    
    def tearDown(self):
        """Clean up"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        os.close(self.db_fd)
        os.unlink(self.db_path)


class TestCampaignWorkflow(IntegrationTestCase):
    """Test complete campaign workflow"""
    
    def test_complete_campaign_lifecycle(self):
        """Test complete campaign from creation to completion"""
        
        # Step 1: Create a campaign
        campaign = CampaignService.create_campaign(
            name="Integration Test Campaign",
            campaign_type="email",
            description="Testing complete workflow",
            track_opens=True,
            track_clicks=True
        )
        
        self.assertEqual(campaign.status, "draft")
        
        # Step 2: Create an email template
        template = Template(
            name="Test Email Template",
            type="email",
            subject="Security Alert: {{target_first_name}}",
            content="""
            <html>
            <body>
                <h2>Security Alert</h2>
                <p>Dear {{target_name}},</p>
                <p>We detected suspicious activity on your account.</p>
                <p><a href="{{tracking_link}}">Verify your account now</a></p>
                <img src="{{tracking_pixel}}" width="1" height="1" />
            </body>
            </html>
            """,
            category="banking",
            difficulty_level="medium"
        )
        
        db.session.add(template)
        db.session.commit()
        
        # Step 3: Add targets to campaign
        csv_content = """email,first_name,last_name,company
john.doe@example.com,John,Doe,TechCorp
jane.smith@example.com,Jane,Smith,BusinessInc
bob.wilson@example.com,Bob,Wilson,StartupLtd"""
        
        stats = CampaignService.add_targets_from_csv(
            campaign.id,
            csv_content
        )
        
        self.assertEqual(stats['added'], 3)
        self.assertEqual(stats['errors'], [])
        
        # Step 4: Start the campaign
        campaign.start()
        self.assertEqual(campaign.status, "active")
        self.assertIsNotNone(campaign.started_at)
        
        # Step 5: Simulate email sending (without actual SMTP)
        targets = Target.query.filter_by(campaign_id=campaign.id).all()
        self.assertEqual(len(targets), 3)
        
        # Mark emails as sent
        for target in targets:
            target.mark_email_sent()
            
            # Create tracking event for email sent
            tracking = Tracking(
                campaign_id=campaign.id,
                event_type="email_sent",
                target_id=target.id,
                ip_address="127.0.0.1",
                user_agent="Test-Agent"
            )
            db.session.add(tracking)
        
        db.session.commit()
        
        # Step 6: Simulate user interactions
        # User 1 opens email
        tracking_service = TrackingService()
        
        with self.app.test_request_context('/'):
            tracking_service.track_email_open(campaign.id, targets[0].id)
            
            # User 1 clicks link
            tracking_service.track_link_click(campaign.id, targets[0].id)
            
            # User 1 submits form
            tracking_service.track_form_submission(
                campaign.id, 
                targets[0].id,
                {'username': 'john.doe', 'password': 'password123'}
            )
        
        # User 2 only opens email
        with self.app.test_request_context('/'):
            tracking_service.track_email_open(campaign.id, targets[1].id)
        
        # Step 7: Capture credentials for user 1
        credential = Credential(
            campaign_id=campaign.id,
            target_id=targets[0].id,
            username="john.doe",
            password="password123",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )
        db.session.add(credential)
        targets[0].mark_credentials_entered()
        db.session.commit()
        
        # Step 8: Verify campaign statistics
        stats = CampaignService.get_campaign_statistics(campaign.id)
        
        self.assertEqual(stats['targets']['total'], 3)
        self.assertEqual(stats['performance']['total_credentials'], 1)
        self.assertGreater(stats['performance']['success_rate'], 0)
        
        # Step 9: Test conversion funnel
        funnel_data = tracking_service.get_conversion_funnel(campaign.id)
        
        self.assertEqual(funnel_data['email_sent'], 3)
        self.assertEqual(funnel_data['email_opened'], 2)  # User 1 and 2
        self.assertEqual(funnel_data['link_clicked'], 1)  # Only user 1
        self.assertEqual(funnel_data['credentials_entered'], 1)  # Only user 1
        
        # Step 10: Complete the campaign
        campaign.complete()
        self.assertEqual(campaign.status, "completed")
        self.assertIsNotNone(campaign.ended_at)
        
        # Step 11: Export campaign data
        csv_export = CampaignService.export_campaign_data(
            campaign.id,
            include_credentials=True
        )
        
        self.assertIn('john.doe@example.com', csv_export)
        self.assertIn('john.doe', csv_export)  # Username should be in export


class TestAPIEndpoints(IntegrationTestCase):
    """Test API endpoints integration"""
    
    def test_campaign_api_endpoints(self):
        """Test campaign API endpoints"""
        
        # Create test campaign
        campaign = CampaignService.create_campaign(
            name="API Test Campaign",
            campaign_type="email"
        )
        
        # Test list campaigns API
        response = self.client.get('/admin/campaigns/api')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('campaigns', data)
        self.assertEqual(len(data['campaigns']), 1)
        
        # Test campaign stats API
        response = self.client.get(f'/admin/campaigns/api/{campaign.id}/stats')
        self.assertEqual(response.status_code, 200)
        
        stats_data = json.loads(response.data)
        self.assertIn('targets', stats_data)
        self.assertIn('performance', stats_data)
    
    def test_template_api_endpoints(self):
        """Test template API endpoints"""
        
        # Create test template
        template = Template(
            name="API Test Template",
            type="email",
            subject="Test Subject",
            content="Hello {{target_name}}, click {{tracking_link}}",
            category="test"
        )
        db.session.add(template)
        db.session.commit()
        
        # Test list templates API
        response = self.client.get('/admin/templates/api')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('templates', data)
        self.assertEqual(len(data['templates']), 1)
        
        # Test get template API
        response = self.client.get(f'/admin/templates/api/{template.id}')
        self.assertEqual(response.status_code, 200)
        
        template_data = json.loads(response.data)
        self.assertEqual(template_data['name'], "API Test Template")


class TestWebhookEndpoints(IntegrationTestCase):
    """Test webhook tracking endpoints"""
    
    def test_tracking_pixel_endpoint(self):
        """Test tracking pixel endpoint"""
        
        # Create test campaign and target
        campaign = CampaignService.create_campaign("Webhook Test", "email")
        target = Target(
            campaign_id=campaign.id,
            email="webhook@example.com"
        )
        db.session.add(target)
        db.session.commit()
        
        # Test tracking pixel request
        response = self.client.get(f'/webhook/pixel.gif?c={campaign.id}&t={target.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'image/gif')
        
        # Verify tracking was recorded
        tracking_events = Tracking.query.filter_by(
            campaign_id=campaign.id,
            target_id=target.id,
            event_type="email_opened"
        ).all()
        
        self.assertEqual(len(tracking_events), 1)
    
    def test_click_tracking_endpoint(self):
        """Test click tracking endpoint"""
        
        # Create test data
        campaign = CampaignService.create_campaign("Click Test", "email")
        target = Target(
            campaign_id=campaign.id,
            email="click@example.com"
        )
        db.session.add(target)
        db.session.commit()
        
        # Test click tracking
        response = self.client.get(
            f'/webhook/click?c={campaign.id}&t={target.id}&url=http://example.com'
        )
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # Verify tracking was recorded
        tracking_events = Tracking.query.filter_by(
            campaign_id=campaign.id,
            target_id=target.id,
            event_type="link_clicked"
        ).all()
        
        self.assertEqual(len(tracking_events), 1)


class TestSecurityIntegration(IntegrationTestCase):
    """Test security features integration"""
    
    def test_input_validation_endpoints(self):
        """Test input validation on endpoints"""
        
        # Test campaign creation with invalid data
        response = self.client.post('/admin/campaigns/create', data={
            'name': '',  # Empty name should fail
            'type': 'email'
        })
        
        # Should stay on same page with error
        self.assertEqual(response.status_code, 200)
        
        # Test with XSS attempt
        response = self.client.post('/admin/campaigns/create', data={
            'name': '<script>alert("xss")</script>',
            'type': 'email',
            'description': 'Test campaign'
        })
        
        # Should either redirect (success) or stay on page (validation error)
        self.assertIn(response.status_code, [200, 302])
        
        # If successful, check that script tags were sanitized
        if response.status_code == 302:
            campaigns = Campaign.query.all()
            if campaigns:
                self.assertNotIn('<script>', campaigns[0].name)
    
    def test_rate_limiting_protection(self):
        """Test basic rate limiting (simplified test)"""
        
        # Create test campaign
        campaign = CampaignService.create_campaign("Rate Test", "email")
        
        # Make multiple rapid requests to stats endpoint
        responses = []
        for i in range(10):
            response = self.client.get(f'/admin/campaigns/api/{campaign.id}/stats')
            responses.append(response.status_code)
        
        # All should succeed in testing (no actual rate limiting configured)
        # This is more of a smoke test
        self.assertTrue(all(status == 200 for status in responses))


class TestErrorHandling(IntegrationTestCase):
    """Test error handling and edge cases"""
    
    def test_nonexistent_resource_handling(self):
        """Test handling of requests for nonexistent resources"""
        
        # Test nonexistent campaign
        response = self.client.get('/admin/campaigns/99999')
        self.assertEqual(response.status_code, 404)
        
        # Test nonexistent template
        response = self.client.get('/admin/templates/99999')
        self.assertEqual(response.status_code, 404)
        
        # Test nonexistent target
        response = self.client.get('/admin/targets/99999')
        self.assertEqual(response.status_code, 404)
    
    def test_invalid_campaign_operations(self):
        """Test invalid campaign operations"""
        
        # Create campaign
        campaign = CampaignService.create_campaign("Error Test", "email")
        
        # Try to start campaign without targets
        with self.assertRaises(ValueError):
            campaign.start()
        
        # Try to complete draft campaign
        with self.assertRaises(ValueError):
            campaign.complete()
    
    def test_database_constraint_violations(self):
        """Test database constraint handling"""
        
        # Create campaign
        campaign1 = CampaignService.create_campaign("Constraint Test", "email")
        
        # Try to create campaign with same name
        with self.assertRaises(ValidationError):
            CampaignService.create_campaign("Constraint Test", "email")


if __name__ == '__main__':
    unittest.main(verbosity=2)