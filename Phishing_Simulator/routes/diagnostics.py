import logging
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from utils.validators import validate_email, validate_phone_number, ValidationError
from services.diagnostic_service import DiagnosticService
from utils.helpers import get_client_ip, log_security_event


# Crearea Blueprint-ului pentru diagnostice
bp = Blueprint('diagnostics', __name__, url_prefix='/admin/diagnostics')

# Inițializează serviciul de diagnostice
diagnostic_service = DiagnosticService()
logger = logging.getLogger(__name__)


@bp.route('/')
def index():
    """
    Dashboard principal pentru diagnostice
    
    Afișează:
    - Status rapid al serviciilor
    - Ultimele diagnostice
    - Butoane pentru testare
    """
    try:
        # Obține status rapid al serviciilor
        service_status = diagnostic_service.get_service_status_summary()
        
        log_security_event('diagnostics_accessed', 'Diagnostics dashboard accessed')
        
        return render_template(
            'admin/diagnostics/index.html',
            service_status=service_status,
            page_title='Service Diagnostics'
        )
        
    except Exception as e:
        logger.error(f"Error loading diagnostics dashboard: {str(e)}")
        flash(f'Error loading diagnostics: {str(e)}', 'error')
        return redirect(url_for('dashboard.index'))


@bp.route('/full')
def full_diagnostics():
    """
    Afișează diagnosticele complete
    """
    try:
        # Rulează diagnosticele complete
        diagnostic_report = diagnostic_service.run_full_diagnostics()
        
        log_security_event('full_diagnostics_run', 'Full diagnostics executed from web interface')
        
        return render_template(
            'admin/diagnostics/full_report.html',
            diagnostic_report=diagnostic_report,
            page_title='Full Diagnostic Report'
        )
        
    except Exception as e:
        logger.error(f"Error running full diagnostics: {str(e)}")
        flash(f'Error running diagnostics: {str(e)}', 'error')
        return redirect(url_for('diagnostics.index'))


@bp.route('/api/status')
def api_status():
    """
    API endpoint pentru status rapid al serviciilor
    """
    try:
        service_status = diagnostic_service.get_service_status_summary()
        return jsonify(service_status)
        
    except Exception as e:
        logger.error(f"Error getting service status: {str(e)}")
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@bp.route('/api/full')
def api_full_diagnostics():
    """
    API endpoint pentru diagnostice complete
    """
    try:
        diagnostic_report = diagnostic_service.run_full_diagnostics()
        return jsonify(diagnostic_report)
        
    except Exception as e:
        logger.error(f"Error running full diagnostics API: {str(e)}")
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@bp.route('/test/email', methods=['GET', 'POST'])
def test_email():
    """
    Testează serviciul de email
    """
    if request.method == 'GET':
        return render_template(
            'admin/diagnostics/test_email.html',
            page_title='Test Email Service'
        )
    
    try:
        # Validează input-ul
        test_email = request.form.get('test_email', '').strip()
        template_name = request.form.get('template_name', 'security').strip()
        
        if not test_email:
            flash('Email address is required', 'error')
            return redirect(url_for('diagnostics.test_email'))
        
        # Validează email-ul
        validate_email(test_email)
        
        # Trimite email-ul de test
        result = diagnostic_service.send_test_email(test_email, template_name)
        
        if result['status'] == 'success':
            flash(f'Test email sent successfully to {test_email}', 'success')
            log_security_event('test_email_sent', f'Test email sent to {test_email}')
        else:
            flash(f'Failed to send test email: {result["message"]}', 'error')
            log_security_event('test_email_failed', f'Test email failed for {test_email}: {result["message"]}')
        
        return render_template(
            'admin/diagnostics/test_email.html',
            page_title='Test Email Service',
            test_result=result
        )
        
    except ValidationError as e:
        flash(f'Invalid email address: {str(e)}', 'error')
        return redirect(url_for('diagnostics.test_email'))
    except Exception as e:
        logger.error(f"Error in test email: {str(e)}")
        flash(f'Error testing email: {str(e)}', 'error')
        return redirect(url_for('diagnostics.test_email'))


@bp.route('/test/sms', methods=['GET', 'POST'])
def test_sms():
    """
    Testează serviciul SMS
    """
    if request.method == 'GET':
        return render_template(
            'admin/diagnostics/test_sms.html',
            page_title='Test SMS Service'
        )
    
    try:
        # Validează input-ul
        test_phone = request.form.get('test_phone', '').strip()
        template_content = request.form.get('template_content', '').strip()
        
        if not test_phone:
            flash('Phone number is required', 'error')
            return redirect(url_for('diagnostics.test_sms'))
        
        # Validează numărul de telefon
        validate_phone_number(test_phone)
        
        # Template default dacă nu e specificat
        if not template_content:
            template_content = "TEST: This is a test SMS from Phishing Simulator. Provider: {{company_name}}"
        
        # Trimite SMS-ul de test
        result = diagnostic_service.send_test_sms(test_phone, template_content)
        
        if result['status'] == 'success':
            flash(f'Test SMS sent successfully to {test_phone}', 'success')
            log_security_event('test_sms_sent', f'Test SMS sent to {test_phone}')
        else:
            flash(f'Failed to send test SMS: {result["message"]}', 'error')
            log_security_event('test_sms_failed', f'Test SMS failed for {test_phone}: {result["message"]}')
        
        return render_template(
            'admin/diagnostics/test_sms.html',
            page_title='Test SMS Service',
            test_result=result,
            template_content=template_content
        )
        
    except ValidationError as e:
        flash(f'Invalid phone number: {str(e)}', 'error')
        return redirect(url_for('diagnostics.test_sms'))
    except Exception as e:
        logger.error(f"Error in test SMS: {str(e)}")
        flash(f'Error testing SMS: {str(e)}', 'error')
        return redirect(url_for('diagnostics.test_sms'))


@bp.route('/api/test/email', methods=['POST'])
def api_test_email():
    """
    API endpoint pentru testarea email-ului
    """
    try:
        data = request.get_json()
        
        if not data or 'test_email' not in data:
            return jsonify({
                'status': 'error',
                'message': 'test_email is required'
            }), 400
        
        test_email = data['test_email'].strip()
        template_name = data.get('template_name', 'security')
        
        # Validează email-ul
        validate_email(test_email)
        
        # Trimite email-ul de test
        result = diagnostic_service.send_test_email(test_email, template_name)
        
        if result['status'] == 'success':
            log_security_event('api_test_email_sent', f'API test email sent to {test_email}')
        
        return jsonify(result)
        
    except ValidationError as e:
        return jsonify({
            'status': 'error',
            'message': f'Invalid email: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 400
    except Exception as e:
        logger.error(f"Error in API test email: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@bp.route('/api/test/sms', methods=['POST'])
def api_test_sms():
    """
    API endpoint pentru testarea SMS-ului
    """
    try:
        data = request.get_json()
        
        if not data or 'test_phone' not in data:
            return jsonify({
                'status': 'error',
                'message': 'test_phone is required'
            }), 400
        
        test_phone = data['test_phone'].strip()
        template_content = data.get('template_content')
        
        # Validează numărul de telefon
        validate_phone_number(test_phone)
        
        # Trimite SMS-ul de test
        result = diagnostic_service.send_test_sms(test_phone, template_content)
        
        if result['status'] == 'success':
            log_security_event('api_test_sms_sent', f'API test SMS sent to {test_phone}')
        
        return jsonify(result)
        
    except ValidationError as e:
        return jsonify({
            'status': 'error',
            'message': f'Invalid phone number: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 400
    except Exception as e:
        logger.error(f"Error in API test SMS: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@bp.route('/configuration')
def configuration():
    """
    Afișează configurația curentă (fără credențiale sensibile)
    """
    try:
        # Rulează doar diagnosticele de configurație
        diagnostic_report = diagnostic_service.run_full_diagnostics()
        
        return render_template(
            'admin/diagnostics/configuration.html',
            diagnostic_report=diagnostic_report,
            page_title='Configuration Overview'
        )
        
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        flash(f'Error loading configuration: {str(e)}', 'error')
        return redirect(url_for('diagnostics.index'))


@bp.route('/connectivity')
def connectivity():
    """
    Testează conectivitatea la servicii externe
    """
    try:
        # Testează doar conectivitatea
        connectivity_result = diagnostic_service.diagnose_connectivity()
        
        return render_template(
            'admin/diagnostics/connectivity.html',
            connectivity_result=connectivity_result,
            page_title='External Connectivity'
        )
        
    except Exception as e:
        logger.error(f"Error testing connectivity: {str(e)}")
        flash(f'Error testing connectivity: {str(e)}', 'error')
        return redirect(url_for('diagnostics.index'))


@bp.route('/export')
def export_diagnostics():
    """
    Exportă raportul de diagnostice ca JSON
    """
    try:
        diagnostic_report = diagnostic_service.run_full_diagnostics()
        
        response = jsonify(diagnostic_report)
        response.headers['Content-Disposition'] = f'attachment; filename=diagnostics_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'
        
        log_security_event('diagnostics_exported', 'Diagnostic report exported')
        
        return response
        
    except Exception as e:
        logger.error(f"Error exporting diagnostics: {str(e)}")
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


# Context processor pentru diagnostice
@bp.context_processor
def inject_diagnostic_data():
    """
    Injectează date de diagnostic în toate template-urile
    """
    try:
        # Doar status rapid pentru a nu încetini paginile
        service_status = diagnostic_service.get_service_status_summary()
        
        return {
            'diagnostic_service_status': service_status.get('services', {}),
            'diagnostic_timestamp': service_status.get('timestamp')
        }
    except Exception as e:
        logger.error(f"Error injecting diagnostic data: {str(e)}")
        return {
            'diagnostic_service_status': {},
            'diagnostic_timestamp': datetime.utcnow().isoformat()
        }