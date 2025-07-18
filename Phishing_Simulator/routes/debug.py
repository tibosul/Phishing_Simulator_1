"""
Debug Routes for SMS and Email Service Testing

This module provides debug endpoints for testing and validating SMS and Email services.
These endpoints are useful for diagnosing configuration issues and testing connectivity.
"""

import logging
from flask import Blueprint, render_template, request, jsonify, current_app, flash, redirect, url_for
from datetime import datetime

from utils.service_tester import ServiceTester
from services.sms_service import SMSService
from services.email_service import EmailService
from utils.validators import validate_email, validate_phone_number, ValidationError
from utils.helpers import log_security_event
from utils.api_responses import success_response, error_response


# Create debug blueprint
debug_bp = Blueprint('debug', __name__, url_prefix='/admin/debug')

# Setup logging
logger = logging.getLogger(__name__)


@debug_bp.route('/')
def debug_dashboard():
    """
    Debug dashboard showing service status and testing tools
    """
    try:
        service_tester = ServiceTester()
        
        # Get comprehensive service status
        service_status = service_tester.test_all_services()
        
        # Get configuration report
        config_report = service_tester.generate_config_report()
        
        return render_template('admin/debug_dashboard.html',
                             service_status=service_status,
                             config_report=config_report,
                             page_title="Service Debug Dashboard")
        
    except Exception as e:
        logger.error(f"Error loading debug dashboard: {str(e)}")
        flash(f'Error loading debug dashboard: {str(e)}', 'error')
        return redirect(url_for('dashboard.index'))


@debug_bp.route('/api/status')
def api_service_status():
    """
    API endpoint for service status (for AJAX updates)
    """
    try:
        service_tester = ServiceTester()
        status = service_tester.test_all_services()
        
        return success_response(
            data=status,
            message="Service status retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting service status: {str(e)}")
        return error_response(f"Error getting service status: {str(e)}", 500)


@debug_bp.route('/api/test-email', methods=['POST'])
def api_test_email():
    """
    API endpoint for testing email sending
    """
    try:
        data = request.get_json()
        test_email = data.get('email')
        template_name = data.get('template', 'security')
        
        if not test_email:
            return error_response("Email address is required", 400)
        
        # Validate email
        try:
            validate_email(test_email)
        except ValidationError as e:
            return error_response(f"Invalid email address: {str(e)}", 400)
        
        # Test email service
        email_service = EmailService()
        
        # Check if email service is configured
        is_configured, config_message = EmailService.validate_email_config()
        if not is_configured:
            return error_response(f"Email service not configured: {config_message}", 400)
        
        # Send test email
        success = email_service.send_test_email(template_name, test_email)
        
        # Log the test
        log_security_event('email_test', f"Email test sent to {test_email}", {
            'template': template_name,
            'success': success
        })
        
        if success:
            return success_response(
                message=f"Test email sent successfully to {test_email}",
                data={'recipient': test_email, 'template': template_name}
            )
        else:
            return error_response("Failed to send test email", 500)
        
    except Exception as e:
        logger.error(f"Error testing email: {str(e)}")
        return error_response(f"Error testing email: {str(e)}", 500)


@debug_bp.route('/api/test-sms', methods=['POST'])
def api_test_sms():
    """
    API endpoint for testing SMS sending
    """
    try:
        data = request.get_json()
        test_phone = data.get('phone')
        test_message = data.get('message', '[TEST] Phishing Simulator test SMS')
        
        if not test_phone:
            return error_response("Phone number is required", 400)
        
        # Validate phone number
        try:
            validate_phone_number(test_phone)
        except ValidationError as e:
            return error_response(f"Invalid phone number: {str(e)}", 400)
        
        # Test SMS service
        sms_service = SMSService()
        
        # Check if SMS service is configured
        is_configured, config_message = SMSService.validate_sms_config()
        if not is_configured:
            return error_response(f"SMS service not configured: {config_message}", 400)
        
        # Send test SMS
        result = sms_service.send_sms(test_phone, f"[TEST] {test_message}")
        
        # Log the test
        log_security_event('sms_test', f"SMS test sent to {test_phone}", {
            'provider': result.get('provider', 'unknown'),
            'success': result.get('success', False)
        })
        
        if result.get('success'):
            return success_response(
                message=f"Test SMS sent successfully to {test_phone}",
                data={
                    'recipient': test_phone,
                    'provider': result.get('provider'),
                    'message_id': result.get('message_id')
                }
            )
        else:
            return error_response("Failed to send test SMS", 500)
        
    except Exception as e:
        logger.error(f"Error testing SMS: {str(e)}")
        return error_response(f"Error testing SMS: {str(e)}", 500)


@debug_bp.route('/api/validate-config')
def api_validate_config():
    """
    API endpoint for validating service configuration
    """
    try:
        service_tester = ServiceTester()
        
        # Test individual services
        sms_status = service_tester.test_sms_service()
        email_status = service_tester.test_email_service()
        
        # Generate configuration report
        config_report = service_tester.generate_config_report()
        
        validation_result = {
            'timestamp': datetime.now().isoformat(),
            'services': {
                'sms': sms_status,
                'email': email_status
            },
            'configuration': config_report,
            'overall_status': 'ok' if (sms_status['status'] == 'ok' and email_status['status'] == 'ok') else 'warning'
        }
        
        return success_response(
            data=validation_result,
            message="Configuration validation completed"
        )
        
    except Exception as e:
        logger.error(f"Error validating configuration: {str(e)}")
        return error_response(f"Error validating configuration: {str(e)}", 500)


@debug_bp.route('/api/connectivity-test')
def api_connectivity_test():
    """
    API endpoint for testing service connectivity
    """
    try:
        service_tester = ServiceTester()
        
        # Test connectivity for both services
        results = {
            'timestamp': datetime.now().isoformat(),
            'tests': {}
        }
        
        # Test SMS connectivity
        try:
            sms_result = service_tester.test_sms_service()
            results['tests']['sms'] = {
                'service': 'SMS',
                'status': sms_result['status'],
                'connectivity': sms_result.get('connectivity', {}),
                'provider': sms_result.get('provider', 'unknown')
            }
        except Exception as e:
            results['tests']['sms'] = {
                'service': 'SMS',
                'status': 'error',
                'error': str(e)
            }
        
        # Test Email connectivity
        try:
            email_result = service_tester.test_email_service()
            results['tests']['email'] = {
                'service': 'Email',
                'status': email_result['status'],
                'connectivity': email_result.get('connectivity', {}),
                'provider': 'SMTP'
            }
        except Exception as e:
            results['tests']['email'] = {
                'service': 'Email',
                'status': 'error',
                'error': str(e)
            }
        
        # Overall status
        sms_ok = results['tests']['sms']['status'] == 'ok'
        email_ok = results['tests']['email']['status'] == 'ok'
        results['overall_status'] = 'ok' if (sms_ok and email_ok) else 'warning' if (sms_ok or email_ok) else 'error'
        
        return success_response(
            data=results,
            message="Connectivity tests completed"
        )
        
    except Exception as e:
        logger.error(f"Error testing connectivity: {str(e)}")
        return error_response(f"Error testing connectivity: {str(e)}", 500)


@debug_bp.route('/service-status')
def service_status_page():
    """
    Dedicated service status page with detailed information
    """
    try:
        service_tester = ServiceTester()
        
        # Get detailed service information
        sms_status = service_tester.test_sms_service()
        email_status = service_tester.test_email_service()
        config_report = service_tester.generate_config_report()
        
        return render_template('admin/service_status.html',
                             sms_status=sms_status,
                             email_status=email_status,
                             config_report=config_report,
                             page_title="Service Status")
        
    except Exception as e:
        logger.error(f"Error loading service status page: {str(e)}")
        flash(f'Error loading service status: {str(e)}', 'error')
        return redirect(url_for('dashboard.index'))


@debug_bp.route('/test-interface')
def test_interface():
    """
    Interactive testing interface for manual testing
    """
    try:
        service_tester = ServiceTester()
        
        # Get current service status for display
        service_status = service_tester.test_all_services()
        
        return render_template('admin/test_interface.html',
                             service_status=service_status,
                             page_title="Service Testing Interface")
        
    except Exception as e:
        logger.error(f"Error loading test interface: {str(e)}")
        flash(f'Error loading test interface: {str(e)}', 'error')
        return redirect(url_for('dashboard.index'))


@debug_bp.route('/configuration-help')
def configuration_help():
    """
    Help page with configuration instructions and troubleshooting
    """
    try:
        # Generate current configuration analysis
        service_tester = ServiceTester()
        config_report = service_tester.generate_config_report()
        
        return render_template('admin/configuration_help.html',
                             config_report=config_report,
                             page_title="Configuration Help")
        
    except Exception as e:
        logger.error(f"Error loading configuration help: {str(e)}")
        flash(f'Error loading configuration help: {str(e)}', 'error')
        return redirect(url_for('dashboard.index'))


# Error handlers for debug blueprint
@debug_bp.errorhandler(404)
def debug_not_found(error):
    """Handle 404 errors in debug routes"""
    return redirect(url_for('debug.debug_dashboard'))


@debug_bp.errorhandler(500)
def debug_internal_error(error):
    """Handle 500 errors in debug routes"""
    logger.error(f"Debug route internal error: {error}")
    flash('An internal error occurred in the debug interface.', 'error')
    return redirect(url_for('debug.debug_dashboard'))