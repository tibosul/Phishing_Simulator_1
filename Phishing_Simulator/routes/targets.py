from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from models.target import Target
from models.campaign import Campaign
from services.campaign_service import CampaignService
from utils.validators import ValidationError, validate_email, validate_phone_number, require_valid_email, validate_backend_input
from utils.helpers import get_client_ip, log_security_event, log_admin_action, sanitize_input
from utils.api_responses import success_response, error_response, validation_error_response, not_found_response, csv_import_response
from utils.database import db
import logging
import csv
import io
import sys

# FIXED: URL prefix to match app.py registration
bp = Blueprint('targets', __name__, url_prefix='/admin/targets')
logger = logging.getLogger(__name__)


def is_ajax_request():
    """
    Helper function to detect if the current request is an AJAX request
    
    Checks for common AJAX indicators:
    - X-Requested-With header
    - Accept header containing application/json
    
    Returns:
        bool: True if request appears to be AJAX, False otherwise
    """
    return (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
            'application/json' in request.headers.get('Accept', ''))


@bp.route('/')
def list_targets():
    """Lista cu toate țintele din sistem - FIXED: returnează HTML"""
    try:
        # Parametri de căutare și filtrare
        search_query = request.args.get('q', '').strip()
        campaign_filter = request.args.get('campaign_id', type=int)
        status_filter = request.args.get('status', '')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        # Query de bază
        targets_query = Target.query
        
        # Aplică filtrele
        if search_query:
            targets_query = targets_query.filter(
                db.or_(
                    Target.email.contains(search_query),
                    Target.first_name.contains(search_query),
                    Target.last_name.contains(search_query),
                    Target.company.contains(search_query)
                )
            )
        
        if campaign_filter:
            targets_query = targets_query.filter_by(campaign_id=campaign_filter)
        
        # Status filtering (mai complex pentru că e computed property)
        if status_filter:
            # Pentru filtering după status, trebuie să luăm toate targets și să filtrăm manual
            all_targets = targets_query.all()
            filtered_targets = [t for t in all_targets if t.status == status_filter]
            
            # Paginare manuală
            start = (page - 1) * per_page
            end = start + per_page
            paginated_targets = filtered_targets[start:end]
            total = len(filtered_targets)
            pages = (total + per_page - 1) // per_page
        else:
            # Paginare normală prin SQLAlchemy
            paginated_result = targets_query.order_by(Target.created_at.desc())\
                .paginate(page=page, per_page=per_page, error_out=False)
            paginated_targets = paginated_result.items
            total = paginated_result.total
            pages = paginated_result.pages
        
        # Statistici generale
        stats = {
            'total_targets': Target.query.count(),
            'contacted': Target.query.filter(
                db.or_(Target.email_sent == True, Target.sms_sent == True)
            ).count(),
            'clicked': Target.query.filter_by(clicked_link=True).count(),
            'compromised': Target.query.filter_by(entered_credentials=True).count(),
            'campaigns': Campaign.query.count()
        }
        
        # Lista campaniilor pentru dropdown filter
        campaigns = Campaign.query.order_by(Campaign.name).all()
        
        # FIXED: Returnează HTML template în loc de JSON
        return render_template('admin/targets.html',
                             targets=paginated_targets,
                             pagination={
                                 'page': page,
                                 'per_page': per_page,
                                 'total': total,
                                 'pages': pages,
                                 'has_prev': page > 1,
                                 'has_next': page < pages
                             },
                             stats=stats,
                             campaigns=campaigns,
                             filters={
                                 'search_query': search_query,
                                 'campaign_filter': campaign_filter,
                                 'status_filter': status_filter
                             })
        
    except Exception as e:
        logger.error(f"Error listing targets: {str(e)}")
        flash('Error loading targets', 'error')
        return render_template('admin/targets.html',
                             targets=[],
                             pagination={},
                             stats={},
                             campaigns=[],
                             filters={})


# API ENDPOINTS (pentru AJAX calls) - separate cu prefix /api
@bp.route('/api')
def api_list_targets():
    """API endpoint pentru listarea țintelor (pentru AJAX)"""
    try:
        # Same logic ca mai sus, dar returnează JSON
        search_query = request.args.get('q', '').strip()
        campaign_filter = request.args.get('campaign_id', type=int)
        status_filter = request.args.get('status', '')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        targets_query = Target.query
        
        if search_query:
            targets_query = targets_query.filter(
                db.or_(
                    Target.email.contains(search_query),
                    Target.first_name.contains(search_query),
                    Target.last_name.contains(search_query),
                    Target.company.contains(search_query)
                )
            )
        
        if campaign_filter:
            targets_query = targets_query.filter_by(campaign_id=campaign_filter)
        
        if status_filter:
            all_targets = targets_query.all()
            filtered_targets = [t for t in all_targets if t.status == status_filter]
            start = (page - 1) * per_page
            end = start + per_page
            paginated_targets = filtered_targets[start:end]
            total = len(filtered_targets)
            pages = (total + per_page - 1) // per_page
        else:
            paginated_result = targets_query.order_by(Target.created_at.desc())\
                .paginate(page=page, per_page=per_page, error_out=False)
            paginated_targets = paginated_result.items
            total = paginated_result.total
            pages = paginated_result.pages
        
        stats = {
            'total_targets': Target.query.count(),
            'contacted': Target.query.filter(
                db.or_(Target.email_sent == True, Target.sms_sent == True)
            ).count(),
            'clicked': Target.query.filter_by(clicked_link=True).count(),
            'compromised': Target.query.filter_by(entered_credentials=True).count(),
            'campaigns': Campaign.query.count()
        }
        
        campaigns = Campaign.query.order_by(Campaign.name).all()
        
        return jsonify({
            'targets': [t.to_dict() for t in paginated_targets],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': pages,
                'has_prev': page > 1,
                'has_next': page < pages
            },
            'stats': stats,
            'campaigns': [{'id': c.id, 'name': c.name, 'status': c.status} for c in campaigns],
            'filters': {
                'search_query': search_query,
                'campaign_filter': campaign_filter,
                'status_filter': status_filter
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing targets: {str(e)}")
        return error_response("Failed to load targets", status_code=500)


@bp.route('/create', methods=['GET', 'POST'])
@validate_backend_input({
    'email': validate_email,
    'phone': lambda x: validate_phone_number(x) if x else True
})
def create_target():
    """FIXED: Creează o nouă țintă - GET returnează form, POST procesează"""
    if request.method == 'GET':
        # Returnează form pentru crearea target-ului
        campaigns = Campaign.query.order_by(Campaign.name).all()
        
        # Check if no campaigns exist
        if not campaigns:
            flash('No campaigns available! Please create a campaign first before adding targets.', 'warning')
        
        return render_template('admin/create_target.html', campaigns=campaigns)
    
    try:
        # Check for backend validation errors
        if hasattr(request, '_validation_errors'):
            for error in request._validation_errors:
                flash(error, 'error')
            campaigns = Campaign.query.order_by(Campaign.name).all()
            return render_template('admin/create_target.html', campaigns=campaigns)
        
        # POST - procesează crearea
        data = request.form.to_dict()
        
        # Validări de bază
        campaign_id = data.get('campaign_id')
        email = data.get('email', '').strip().lower()
        
        if not campaign_id:
            flash('Campaign is required', 'error')
            campaigns = Campaign.query.order_by(Campaign.name).all()
            return render_template('admin/create_target.html', campaigns=campaigns)
        
        if not email:
            flash('Email is required', 'error')
            campaigns = Campaign.query.order_by(Campaign.name).all()
            return render_template('admin/create_target.html', campaigns=campaigns)
        
        # Verifică dacă campania există
        campaign = db.session.get(Campaign, campaign_id)
        if not campaign:
            flash('Campaign not found', 'error')
            campaigns = Campaign.query.order_by(Campaign.name).all()
            return render_template('admin/create_target.html', campaigns=campaigns)
        
        # Validează email-ul
        try:
            validate_email(email)
        except ValidationError as e:
            flash(f'Invalid email: {str(e)}', 'error')
            campaigns = Campaign.query.order_by(Campaign.name).all()
            return render_template('admin/create_target.html', campaigns=campaigns)
        
        # Verifică duplicatele în campania respectivă
        existing = Target.get_by_email_and_campaign(email, campaign_id)
        if existing:
            flash(f'Target with email {email} already exists in this campaign', 'error')
            campaigns = Campaign.query.order_by(Campaign.name).all()
            return render_template('admin/create_target.html', campaigns=campaigns)
        
        # Date opționale - sanitizate
        target_data = {}
        optional_fields = ['first_name', 'last_name', 'company', 'position', 'phone', 'notes']
        
        for field in optional_fields:
            value = data.get(field, '').strip()
            if value:
                target_data[field] = sanitize_input(value)
        
        # Validează telefonul dacă e furnizat
        if 'phone' in target_data:
            try:
                validate_phone_number(target_data['phone'])
            except ValidationError as e:
                flash(f'Invalid phone: {str(e)}', 'error')
                campaigns = Campaign.query.order_by(Campaign.name).all()
                return render_template('admin/create_target.html', campaigns=campaigns)
        
        # Creează ținta folosind CampaignService
        target = CampaignService.add_single_target(campaign_id, email, **target_data)
        
        # Log admin action
        log_admin_action('create', 'target', target.id, f'Email: {email}, Campaign: {campaign.name}')
        
        flash(f'Target {email} added to campaign "{campaign.name}"', 'success')
        return redirect(url_for('targets.list_targets'))
        
    except ValidationError as e:
        flash(str(e), 'error')
        campaigns = Campaign.query.order_by(Campaign.name).all()
        return render_template('admin/create_target.html', campaigns=campaigns)
    except Exception as e:
        logger.error(f"Error creating target: {str(e)}")
        flash('Failed to create target', 'error')
        campaigns = Campaign.query.order_by(Campaign.name).all()
        return render_template('admin/create_target.html', campaigns=campaigns)


@bp.route('/<int:target_id>')
def view_target(target_id):
    """FIXED: Returnează detaliile complete ale unei ținte - HTML page"""
    try:
        target = Target.query.get_or_404(target_id)
        
        # Obține tracking summary complet
        tracking_summary = target.get_tracking_summary()
        
        # Informații despre campanie
        campaign_info = {
            'id': target.campaign.id,
            'name': target.campaign.name,
            'type': target.campaign.type,
            'status': target.campaign.status,
            'created_at': target.campaign.created_at.isoformat() if target.campaign.created_at else None
        }
        
        # Credențiale capturate (fără parole în clar)
        credentials_info = []
        for cred in target.captured_credentials:
            credentials_info.append({
                'id': cred.id,
                'username': cred.username,
                'password_strength': cred.password_strength,
                'risk_score': cred.risk_score,
                'captured_at': cred.captured_at.isoformat() if cred.captured_at else None,
                'is_real_credential': cred.is_real_credential
            })
        
        return render_template('admin/target_detail.html',
                             target=target,
                             campaign=campaign_info,
                             tracking_summary=tracking_summary,
                             credentials=credentials_info)
        
    except Exception as e:
        logger.error(f"Error getting target {target_id}: {str(e)}")
        flash('Target not found', 'error')
        return redirect(url_for('targets.list_targets'))


# Rest of API endpoints remain as JSON (for AJAX)
@bp.route('/api/<int:target_id>')
def api_get_target(target_id):
    """API endpoint pentru detaliile unei ținte"""
    try:
        target = Target.query.get_or_404(target_id)
        
        tracking_summary = target.get_tracking_summary()
        
        campaign_info = {
            'id': target.campaign.id,
            'name': target.campaign.name,
            'type': target.campaign.type,
            'status': target.campaign.status,
            'created_at': target.campaign.created_at.isoformat() if target.campaign.created_at else None
        }
        
        credentials_info = []
        for cred in target.captured_credentials:
            credentials_info.append({
                'id': cred.id,
                'username': cred.username,
                'password_strength': cred.password_strength,
                'risk_score': cred.risk_score,
                'captured_at': cred.captured_at.isoformat() if cred.captured_at else None,
                'is_real_credential': cred.is_real_credential
            })
        
        return jsonify({
            'target': target.to_dict(),
            'campaign': campaign_info,
            'tracking_summary': tracking_summary,
            'credentials': credentials_info
        })
        
    except Exception as e:
        logger.error(f"Error getting target {target_id}: {str(e)}")
        return jsonify({'error': 'Target not found'}), 404


# Continue with other endpoints...
@bp.route('/api/<int:target_id>', methods=['PUT'])
@validate_backend_input({
    'phone': lambda x: validate_phone_number(x) if x else True
})
def api_update_target(target_id):
    """API endpoint pentru actualizarea unei ținte"""
    try:
        # Check for backend validation errors
        if hasattr(request, '_validation_errors'):
            return validation_error_response("Input validation failed", request._validation_errors)
        
        target = Target.query.get_or_404(target_id)
        data = request.get_json()
        
        if not data:
            return validation_error_response("No data provided")
        
        updatable_fields = ['first_name', 'last_name', 'company', 'position', 'phone', 'notes']
        update_data = {}
        
        for field in updatable_fields:
            if field in data:
                value = data[field]
                if value:
                    value = sanitize_input(value.strip())
                update_data[field] = value
        
        if 'phone' in update_data and update_data['phone']:
            try:
                validate_phone_number(update_data['phone'])
            except ValidationError as e:
                return validation_error_response(f"Invalid phone number", [str(e)])
        
        updated = target.update_profile(**update_data)
        
        if updated:
            log_security_event('target_updated', f'Target {target.email} updated', get_client_ip())
            log_admin_action('update', 'target', target.id, f'Email: {target.email}')
            message = f'Target {target.email} updated successfully'
        else:
            message = f'No changes made to target {target.email}'
        
        return success_response(
            data={
                'target': target.to_dict(),
                'updated': updated
            },
            message=message
        )
        
    except Exception as e:
        logger.error(f"Error updating target {target_id}: {str(e)}")
        return error_response("Failed to update target", status_code=500)


@bp.route('/api/<int:target_id>', methods=['DELETE'])
def api_delete_target(target_id):
    """API endpoint pentru ștergerea unei ținte"""
    try:
        target = Target.query.get_or_404(target_id)
        target_email = target.email
        campaign_name = target.campaign.name if target.campaign else 'Unknown'
        
        db.session.delete(target)
        db.session.commit()
        
        log_security_event('target_deleted', f'Target {target_email} deleted from campaign {campaign_name}', get_client_ip())
        log_admin_action('delete', 'target', target_id, f'Email: {target_email}, Campaign: {campaign_name}')
        
        return success_response(message=f'Target {target_email} deleted successfully')
        
    except Exception as e:
        logger.error(f"Error deleting target {target_id}: {str(e)}")
        return error_response("Failed to delete target", status_code=500)


# Additional routes continue as API endpoints...
@bp.route('/test-debug')
def test_debug():
    """Simple test route to verify our code is being executed"""
    print("=== TEST DEBUG ROUTE HIT ===", file=sys.stderr, flush=True)
    return "TEST DEBUG WORKS"

@bp.route('/upload', methods=['GET', 'POST'])
def upload_targets():
    """Standalone upload route that allows selecting any campaign for CSV upload"""
    import sys
    print("=== ENTERING upload_targets route ===", file=sys.stderr, flush=True)
    try:
        print("=== ENTERING upload_targets route TRY BLOCK ===", file=sys.stderr, flush=True)
        logger.info("Accessing upload_targets route")
        if request.method == 'GET':
            print("=== GET request ===", file=sys.stderr, flush=True)
            # Get all campaigns for selection dropdown
            try:
                campaigns = Campaign.query.order_by(Campaign.name).all()
                print(f"=== Found {len(campaigns) if campaigns else 'None'} campaigns for dropdown ===", file=sys.stderr, flush=True)
                logger.info(f"Found {len(campaigns) if campaigns else 'None'} campaigns for dropdown")
                
                # Log campaigns for debugging
                if campaigns:
                    for c in campaigns:
                        print(f"Campaign: {c.name} (ID: {c.id})", file=sys.stderr, flush=True)
                        logger.info(f"Campaign: {c.name} (ID: {c.id})")
                else:
                    print("=== campaigns is None or empty ===", file=sys.stderr, flush=True)
                
            except Exception as e:
                print(f"=== ERROR querying campaigns: {e} ===", file=sys.stderr, flush=True)
                logger.error(f"Error querying campaigns: {e}")
                campaigns = []
            
            # Check if no campaigns exist and show appropriate message
            if not campaigns:
                flash('No campaigns available! Please create a campaign first before uploading targets.', 'warning')
                logger.warning("No campaigns available for target upload")
            
            print("=== ABOUT TO RENDER TEMPLATE ===", file=sys.stderr, flush=True)
            print(f"=== campaigns variable type: {type(campaigns)}, value: {campaigns} ===", file=sys.stderr, flush=True)
            return render_template('admin/upload_targets.html', campaigns=campaigns)
        
        # POST - handle the CSV upload
        print("=== POST request for CSV upload ===", file=sys.stderr, flush=True)
        
        # Detect if this is an AJAX request
        is_ajax = is_ajax_request()
        print(f"=== Is AJAX request: {is_ajax} ===", file=sys.stderr, flush=True)
        
        # Check if campaigns exist first
        campaigns = Campaign.query.order_by(Campaign.name).all()
        if not campaigns:
            error_msg = 'No campaigns available! Please create a campaign first.'
            flash(error_msg, 'error')
            if is_ajax:
                return jsonify({
                    'success': False,
                    'error': error_msg
                }), 400
            return render_template('admin/upload_targets.html', campaigns=[])
        
        campaign_id = request.form.get('campaign_id')
        if not campaign_id:
            error_msg = 'Please select a campaign'
            flash(error_msg, 'error')
            if is_ajax:
                return jsonify({
                    'success': False,
                    'error': error_msg
                }), 400
            return render_template('admin/upload_targets.html', campaigns=campaigns)
        
        # Verifică dacă campania există
        campaign = db.session.get(Campaign, campaign_id)
        if not campaign:
            error_msg = 'Selected campaign not found'
            flash(error_msg, 'error')
            if is_ajax:
                return jsonify({
                    'success': False,
                    'error': error_msg
                }), 404
            campaigns = Campaign.query.order_by(Campaign.name).all()
            return render_template('admin/upload_targets.html', campaigns=campaigns)
        
        # Verifică dacă fișierul a fost uploadat
        if 'csv_file' not in request.files:
            error_msg = 'No file selected'
            flash(error_msg, 'error')
            if is_ajax:
                return jsonify({
                    'success': False,
                    'error': error_msg
                }), 400
            campaigns = Campaign.query.order_by(Campaign.name).all()
            return render_template('admin/upload_targets.html', campaigns=campaigns, selected_campaign=campaign)
        
        file = request.files['csv_file']
        if file.filename == '':
            error_msg = 'No file selected'
            flash(error_msg, 'error')
            if is_ajax:
                return jsonify({
                    'success': False,
                    'error': error_msg
                }), 400
            campaigns = Campaign.query.order_by(Campaign.name).all()
            return render_template('admin/upload_targets.html', campaigns=campaigns, selected_campaign=campaign)
        
        # Verifică extensia și mărimea fișierului
        if not file.filename.lower().endswith('.csv'):
            error_msg = 'Please upload a CSV file'
            flash(error_msg, 'error')
            if is_ajax:
                return jsonify({
                    'success': False,
                    'error': error_msg
                }), 400
            campaigns = Campaign.query.order_by(Campaign.name).all()
            return render_template('admin/upload_targets.html', campaigns=campaigns, selected_campaign=campaign)
        
        # Verifică mărimea fișierului (5MB limit)
        max_file_size = 5 * 1024 * 1024  # 5MB
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > max_file_size:
            error_msg = f'File too large. Maximum size allowed: {max_file_size // 1024 // 1024}MB'
            flash(error_msg, 'error')
            if is_ajax:
                return jsonify({
                    'success': False,
                    'error': error_msg
                }), 400
            campaigns = Campaign.query.order_by(Campaign.name).all()
            return render_template('admin/upload_targets.html', campaigns=campaigns, selected_campaign=campaign)
        
        # Citește conținutul
        csv_content = file.read().decode('utf-8')
        
        # Verifică numărul de rânduri pentru prevenirea DoS
        row_count = len(csv_content.split('\n')) - 1  # -1 for header
        max_rows = 10000
        if row_count > max_rows:
            error_msg = f'CSV has too many rows. Maximum allowed: {max_rows}'
            flash(error_msg, 'error')
            if is_ajax:
                return jsonify({
                    'success': False,
                    'error': error_msg
                }), 400
            campaigns = Campaign.query.order_by(Campaign.name).all()
            return render_template('admin/upload_targets.html', campaigns=campaigns, selected_campaign=campaign)
        
        # Opțiuni
        skip_duplicates = request.form.get('skip_duplicates') == 'on'
        
        # Procesează CSV-ul
        stats = CampaignService.add_targets_from_csv(
            campaign_id=campaign_id,
            csv_content=csv_content,
            skip_duplicates=skip_duplicates
        )
        
        # Log the activity
        log_security_event('targets_uploaded', f'{stats["added"]} targets added to campaign "{campaign.name}"', get_client_ip())
        log_admin_action('csv_upload', 'targets', campaign.id, 
                        f'Campaign: {campaign.name}, Added: {stats["added"]}, Skipped: {stats["skipped"]}, Errors: {len(stats["errors"])}')
        
        # For AJAX requests, return JSON response
        if is_ajax:
            success_msg = []
            info_msg = []
            warning_msg = []
            
            if stats['added'] > 0:
                success_msg.append(f'Successfully added {stats["added"]} targets to campaign "{campaign.name}"')
            
            if stats['skipped'] > 0:
                info_msg.append(f'{stats["skipped"]} targets were skipped (duplicates)')
            
            if stats['errors']:
                warning_msg.append(f'{len(stats["errors"])} errors occurred during import')
            
            return jsonify({
                'success': True,
                'message': 'Targets imported successfully',
                'stats': {
                    'added': stats['added'],
                    'skipped': stats['skipped'],
                    'errors': len(stats['errors']),
                    'error_details': stats['errors'][:10] if stats['errors'] else []  # Limit error details
                },
                'campaign': {
                    'id': campaign.id,
                    'name': campaign.name
                },
                'messages': {
                    'success': success_msg,
                    'info': info_msg,
                    'warning': warning_msg
                }
            })
        
        # For regular form submissions, return HTML template with flash messages
        if stats['added'] > 0:
            flash(f'Successfully added {stats["added"]} targets to campaign "{campaign.name}"', 'success')
        
        if stats['skipped'] > 0:
            flash(f'{stats["skipped"]} targets were skipped (duplicates)', 'info')
        
        if stats['errors']:
            flash(f'{len(stats["errors"])} errors occurred during import', 'warning')
        
        campaigns = Campaign.query.order_by(Campaign.name).all()
        return render_template('admin/upload_targets.html', 
                             campaigns=campaigns, 
                             selected_campaign=campaign,
                             upload_stats=stats)
        
    except ValidationError as e:
        error_msg = str(e)
        if is_ajax_request():
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        flash(error_msg, 'error')
        campaigns = Campaign.query.order_by(Campaign.name).all()
        return render_template('admin/upload_targets.html', campaigns=campaigns)
    except Exception as e:
        logger.error(f"Error uploading targets: {str(e)}")
        error_msg = 'Error processing CSV file'
        if is_ajax_request():
            return jsonify({
                'success': False,
                'error': error_msg,
                'details': str(e) if logger.level <= logging.DEBUG else None
            }), 500
        flash(error_msg, 'error')
        campaigns = Campaign.query.order_by(Campaign.name).all()
        return render_template('admin/upload_targets.html', campaigns=campaigns)


@bp.route('/api/bulk-import', methods=['POST'])
def api_bulk_import_targets():
    """API endpoint pentru import în masă din CSV"""
    try:
        data = request.get_json()
        
        campaign_id = data.get('campaign_id')
        csv_content = data.get('csv_content', '')
        skip_duplicates = data.get('skip_duplicates', True)
        
        if not campaign_id:
            return validation_error_response("Campaign ID is required")
        
        if not csv_content:
            return validation_error_response("CSV content is required")
        
        campaign = db.session.get(Campaign, campaign_id)
        if not campaign:
            return not_found_response("Campaign")
        
        # Enhanced CSV import with security limits
        stats = CampaignService.add_targets_from_csv(
            campaign_id=campaign_id,
            csv_content=csv_content,
            skip_duplicates=skip_duplicates,
            max_rows=10000,  # Explicit limit
            max_file_size=5*1024*1024  # 5MB limit
        )
        
        log_security_event('targets_bulk_imported', 
                          f'{stats["added"]} targets imported to campaign {campaign.name}', 
                          get_client_ip())
        
        return csv_import_response(stats, campaign.name)
        
    except ValidationError as e:
        return validation_error_response(str(e))
    except Exception as e:
        logger.error(f"Error in bulk import: {str(e)}")
        return error_response("Bulk import failed", status_code=500)