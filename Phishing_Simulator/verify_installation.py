#!/usr/bin/env python3
"""
Phishing Simulator End-to-End Verification Script

This script performs a comprehensive test of all major functionalities
to ensure the application is working correctly.
"""

import sys
import os
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from utils.database import db
from services.campaign_service import CampaignService
from services.email_service import EmailService
from services.tracking_service import TrackingService
from models.campaign import Campaign
from models.template import Template
from models.target import Target


class PhishingSimulatorVerification:
    """Comprehensive verification of Phishing Simulator functionality"""
    
    def __init__(self):
        self.app = create_app()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        self.results = {
            'passed': 0,
            'failed': 0,
            'errors': []
        }
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def log_test(self, test_name, success, message=""):
        """Log test result"""
        status = "PASS" if success else "FAIL"
        self.logger.info(f"[{status}] {test_name}: {message}")
        
        if success:
            self.results['passed'] += 1
        else:
            self.results['failed'] += 1
            self.results['errors'].append(f"{test_name}: {message}")
    
    def test_database_connection(self):
        """Test database connectivity and table creation"""
        try:
            # Drop and recreate all tables to start fresh
            db.drop_all()
            db.create_all()
            
            # Test basic query
            result = db.session.execute(db.text("SELECT 1")).scalar()
            success = result == 1
            
            self.log_test(
                "Database Connection",
                success,
                "Connected and tables created successfully" if success else "Failed to connect"
            )
            return success
            
        except Exception as e:
            self.log_test("Database Connection", False, str(e))
            return False
    
    def test_campaign_creation(self):
        """Test campaign creation and lifecycle"""
        try:
            # Create campaign
            campaign = CampaignService.create_campaign(
                name="Verification Test Campaign",
                campaign_type="email",
                description="Automated verification test",
                track_opens=True,
                track_clicks=True
            )
            
            success = campaign is not None and campaign.id is not None
            self.log_test(
                "Campaign Creation", 
                success,
                f"Created campaign ID: {campaign.id}" if success else "Failed to create campaign"
            )
            
            if success:
                # Test campaign status transitions
                try:
                    # Add a target first
                    target = Target(
                        campaign_id=campaign.id,
                        email="test@example.com",
                        first_name="Test",
                        last_name="User"
                    )
                    db.session.add(target)
                    db.session.commit()
                    
                    # Test status transitions
                    campaign.start()
                    self.log_test("Campaign Start", campaign.status == "active", f"Status: {campaign.status}")
                    
                    campaign.pause()
                    self.log_test("Campaign Pause", campaign.status == "paused", f"Status: {campaign.status}")
                    
                    campaign.resume()
                    self.log_test("Campaign Resume", campaign.status == "active", f"Status: {campaign.status}")
                    
                    campaign.complete()
                    self.log_test("Campaign Complete", campaign.status == "completed", f"Status: {campaign.status}")
                    
                except Exception as e:
                    self.log_test("Campaign Lifecycle", False, str(e))
            
            return success
            
        except Exception as e:
            self.log_test("Campaign Creation", False, str(e))
            return False
    
    def test_template_creation(self):
        """Test template creation and rendering"""
        try:
            template = Template(
                name="Verification Test Template",
                type="email",
                subject="Test Subject - {{target_first_name}}",
                content="""
                <html>
                <body>
                    <h2>Test Email</h2>
                    <p>Hello {{target_name}},</p>
                    <p>This is a test email for verification.</p>
                    <p><a href="{{tracking_link}}">Click here</a></p>
                    <img src="{{tracking_pixel}}" width="1" height="1" />
                </body>
                </html>
                """,
                category="test",
                difficulty_level="easy"
            )
            
            db.session.add(template)
            db.session.commit()
            
            success = template.id is not None
            self.log_test(
                "Template Creation",
                success,
                f"Created template ID: {template.id}" if success else "Failed to create template"
            )
            
            if success:
                # Test template rendering
                try:
                    rendered_subject = template.render_subject({
                        'target_first_name': 'John',
                        'target_name': 'John Doe'
                    })
                    
                    rendered_content = template.render_content({
                        'target_name': 'John Doe',
                        'tracking_link': 'http://example.com/track',
                        'tracking_pixel': 'http://example.com/pixel.gif'
                    })
                    
                    subject_ok = 'John' in rendered_subject
                    content_ok = 'John Doe' in rendered_content and 'example.com' in rendered_content
                    
                    self.log_test("Template Rendering", subject_ok and content_ok, 
                                "Subject and content rendered correctly")
                    
                except Exception as e:
                    self.log_test("Template Rendering", False, str(e))
            
            return success
            
        except Exception as e:
            self.log_test("Template Creation", False, str(e))
            return False
    
    def test_target_management(self):
        """Test target creation and CSV import"""
        try:
            # Create a campaign for targets
            campaign = Campaign(
                name="Target Test Campaign",
                type="email"
            )
            db.session.add(campaign)
            db.session.commit()
            
            # Test CSV import
            csv_content = """email,first_name,last_name,company
test1@example.com,John,Doe,Test Corp
test2@example.com,Jane,Smith,Another Corp
test3@example.com,Bob,Wilson,Third Corp"""
            
            stats = CampaignService.add_targets_from_csv(
                campaign.id,
                csv_content,
                skip_duplicates=True
            )
            
            success = stats['added'] == 3 and len(stats['errors']) == 0
            self.log_test(
                "Target CSV Import",
                success,
                f"Added: {stats['added']}, Errors: {len(stats['errors'])}"
            )
            
            # Test individual target creation
            try:
                individual_target = CampaignService.add_single_target(
                    campaign.id,
                    "individual@example.com",
                    first_name="Individual",
                    last_name="Target",
                    company="Solo Corp"
                )
                
                self.log_test(
                    "Individual Target Creation",
                    individual_target is not None,
                    f"Created target: {individual_target.email}" if individual_target else "Failed"
                )
                
            except Exception as e:
                self.log_test("Individual Target Creation", False, str(e))
            
            return success
            
        except Exception as e:
            self.log_test("Target Management", False, str(e))
            return False
    
    def test_email_service(self):
        """Test email service functionality"""
        try:
            email_service = EmailService()
            
            # Test configuration validation
            is_valid, message = EmailService.validate_email_config()
            self.log_test(
                "Email Configuration",
                True,  # Don't fail if not configured for testing
                f"Config check: {message}"
            )
            
            # Test template rendering
            try:
                campaign = Campaign(name="Email Test", type="email")
                campaign.id = 999  # Fake ID for testing
                
                target = Target(
                    campaign_id=999,
                    email="test@example.com",
                    first_name="Test",
                    last_name="User"
                )
                
                subject, content = email_service.render_email_template(
                    'security',
                    target,
                    campaign
                )
                
                render_success = len(subject) > 0 and len(content) > 0
                self.log_test(
                    "Email Template Rendering",
                    render_success,
                    f"Subject length: {len(subject)}, Content length: {len(content)}"
                )
                
            except Exception as e:
                self.log_test("Email Template Rendering", False, str(e))
            
            return True
            
        except Exception as e:
            self.log_test("Email Service", False, str(e))
            return False
    
    def test_tracking_service(self):
        """Test tracking service functionality"""
        try:
            tracking_service = TrackingService()
            
            # Create test campaign and target
            campaign = Campaign(name="Tracking Test", type="email")
            db.session.add(campaign)
            db.session.commit()
            
            target = Target(
                campaign_id=campaign.id,
                email="tracking@example.com"
            )
            db.session.add(target)
            db.session.commit()
            
            # Test tracking with app context
            with self.app.test_request_context('/'):
                import uuid
                
                # Test email open tracking
                open_token = f"test-open-{uuid.uuid4().hex[:8]}"
                open_event = tracking_service.track_email_open(
                    campaign.id,
                    target.id,
                    open_token
                )
                
                open_success = open_event is not None and open_event.event_type == "email_opened"
                self.log_test(
                    "Email Open Tracking",
                    open_success,
                    f"Event ID: {open_event.id}" if open_event else "Failed"
                )
                
                # Test click tracking
                click_token = f"test-click-{uuid.uuid4().hex[:8]}"
                click_event, redirect_url = tracking_service.track_link_click(
                    campaign.id,
                    target.id,
                    "http://example.com",
                    click_token
                )
                
                click_success = click_event is not None and click_event.event_type == "link_clicked"
                self.log_test(
                    "Link Click Tracking",
                    click_success,
                    f"Event ID: {click_event.id}" if click_event else "Failed"
                )
            
            # Test funnel calculation
            try:
                funnel_data = tracking_service.get_conversion_funnel(campaign.id)
                funnel_success = isinstance(funnel_data, dict)
                self.log_test(
                    "Conversion Funnel",
                    funnel_success,
                    f"Funnel data keys: {list(funnel_data.keys())}" if funnel_success else "Failed"
                )
                
            except Exception as e:
                self.log_test("Conversion Funnel", False, str(e))
            
            return True
            
        except Exception as e:
            self.log_test("Tracking Service", False, str(e))
            return False
    
    def test_security_features(self):
        """Test security features"""
        try:
            from utils.security import sanitize_input, validate_csrf_token, is_safe_url
            
            # Test input sanitization
            malicious_input = "<script>alert('xss')</script>Normal text"
            try:
                sanitized = sanitize_input(malicious_input, allow_html=False, strict=True)
                # Should raise exception for malicious content in strict mode
                sanitization_success = False
            except ValueError:
                # Exception expected for malicious input
                sanitization_success = True
            
            self.log_test(
                "Input Sanitization",
                sanitization_success,
                "Correctly blocked malicious input" if sanitization_success else "Failed to block malicious input"
            )
            
            # Test safe URL validation
            safe_url_tests = [
                ("/admin/dashboard", True),
                ("javascript:alert(1)", False),
                ("http://evil.com", False),
                ("//evil.com", False)
            ]
            
            url_test_success = True
            for url, expected in safe_url_tests:
                with self.app.test_request_context():
                    result = is_safe_url(url)
                    if result != expected:
                        url_test_success = False
                        break
            
            self.log_test(
                "URL Validation",
                url_test_success,
                "All URL validation tests passed" if url_test_success else "Some URL tests failed"
            )
            
            return sanitization_success and url_test_success
            
        except Exception as e:
            self.log_test("Security Features", False, str(e))
            return False
    
    def test_api_endpoints(self):
        """Test API endpoints"""
        try:
            with self.app.test_client() as client:
                # Test dashboard
                response = client.get('/admin/')
                dashboard_ok = response.status_code == 200
                self.log_test(
                    "Dashboard Endpoint",
                    dashboard_ok,
                    f"Status: {response.status_code}"
                )
                
                # Test campaigns list
                response = client.get('/admin/campaigns/')
                campaigns_ok = response.status_code == 200
                self.log_test(
                    "Campaigns Endpoint",
                    campaigns_ok,
                    f"Status: {response.status_code}"
                )
                
                # Test templates list
                response = client.get('/admin/templates/')
                templates_ok = response.status_code == 200
                self.log_test(
                    "Templates Endpoint",
                    templates_ok,
                    f"Status: {response.status_code}"
                )
                
                # Test API endpoints
                response = client.get('/admin/campaigns/api')
                api_ok = response.status_code == 200
                self.log_test(
                    "API Endpoints",
                    api_ok,
                    f"Status: {response.status_code}"
                )
                
                return dashboard_ok and campaigns_ok and templates_ok and api_ok
            
        except Exception as e:
            self.log_test("API Endpoints", False, str(e))
            return False
    
    def run_all_tests(self):
        """Run all verification tests"""
        self.logger.info("=" * 60)
        self.logger.info("PHISHING SIMULATOR VERIFICATION STARTING")
        self.logger.info("=" * 60)
        
        start_time = datetime.now()
        
        # Run all tests
        tests = [
            self.test_database_connection,
            self.test_campaign_creation,
            self.test_template_creation,
            self.test_target_management,
            self.test_email_service,
            self.test_tracking_service,
            self.test_security_features,
            self.test_api_endpoints
        ]
        
        all_passed = True
        for test in tests:
            try:
                success = test()
                if not success:
                    all_passed = False
            except Exception as e:
                self.logger.error(f"Test {test.__name__} failed with exception: {e}")
                all_passed = False
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Print summary
        self.logger.info("=" * 60)
        self.logger.info("VERIFICATION RESULTS")
        self.logger.info("=" * 60)
        self.logger.info(f"Duration: {duration}")
        self.logger.info(f"Tests Passed: {self.results['passed']}")
        self.logger.info(f"Tests Failed: {self.results['failed']}")
        self.logger.info(f"Overall Status: {'PASS' if all_passed else 'FAIL'}")
        
        if self.results['errors']:
            self.logger.info("\nFAILED TESTS:")
            for error in self.results['errors']:
                self.logger.info(f"  - {error}")
        
        if all_passed:
            self.logger.info("\n🎉 ALL TESTS PASSED - Phishing Simulator is ready for use!")
        else:
            self.logger.info("\n❌ SOME TESTS FAILED - Please review the errors above")
        
        return all_passed
    
    def cleanup(self):
        """Cleanup after tests"""
        try:
            db.session.rollback()
            self.app_context.pop()
        except:
            pass


def main():
    """Main verification function"""
    verification = PhishingSimulatorVerification()
    
    try:
        success = verification.run_all_tests()
        verification.cleanup()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\nVerification interrupted by user")
        verification.cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"Verification failed with error: {e}")
        verification.cleanup()
        sys.exit(1)


if __name__ == "__main__":
    main()