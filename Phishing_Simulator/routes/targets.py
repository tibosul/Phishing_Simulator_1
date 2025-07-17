from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from models.target import Target
from models.campaign import Campaign
from services.campaign_service import CampaignService
from utils.validators import ValidationError, validate_email, validate_phone_number
from utils.helpers import get_client_ip, log_security_event, sanitize_input
from utils.database import db
import logging
import csv
import io

# FIXED: URL prefix to match app.py registration
bp = Blueprint('targets', __name__, url_prefix='/admin/targets')
logger = logging.getLogger(__name__)


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
        return jsonify({'error': 'Failed to load targets'}), 500


@bp.route('/create', methods=['GET', 'POST'])
def create_target():
    """FIXED: Creează o nouă țintă - GET returnează form, POST procesează"""
    if request.method == 'GET':
        # Returnează form pentru crearea target-ului
        campaigns = Campaign.query.order_by(Campaign.name).all()
        return render_template('admin/create_target.html', campaigns=campaigns)
    
    try:
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
def api_update_target(target_id):
    """API endpoint pentru actualizarea unei ținte"""
    try:
        target = Target.query.get_or_404(target_id)
        data = request.get_json()
        
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
                return jsonify({'error': f'Invalid phone: {str(e)}'}), 400
        
        updated = target.update_profile(**update_data)
        
        if updated:
            log_security_event('target_updated', f'Target {target.email} updated', get_client_ip())
            message = f'Target {target.email} updated successfully'
        else:
            message = f'No changes made to target {target.email}'
        
        return jsonify({
            'success': True,
            'target': target.to_dict(),
            'updated': updated,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"Error updating target {target_id}: {str(e)}")
        return jsonify({'error': 'Failed to update target'}), 500


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
        
        return jsonify({
            'success': True,
            'message': f'Target {target_email} deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting target {target_id}: {str(e)}")
        return jsonify({'error': 'Failed to delete target'}), 500


# Additional routes continue as API endpoints...
@bp.route('/api/bulk-import', methods=['POST'])
def api_bulk_import_targets():
    """API endpoint pentru import în masă din CSV"""
    try:
        data = request.get_json()
        
        campaign_id = data.get('campaign_id')
        csv_content = data.get('csv_content', '')
        skip_duplicates = data.get('skip_duplicates', True)
        
        if not campaign_id:
            return jsonify({'error': 'Campaign ID is required'}), 400
        
        if not csv_content:
            return jsonify({'error': 'CSV content is required'}), 400
        
        campaign = db.session.get(Campaign, campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        stats = CampaignService.add_targets_from_csv(
            campaign_id=campaign_id,
            csv_content=csv_content,
            skip_duplicates=skip_duplicates
        )
        
        log_security_event('targets_bulk_imported', 
                          f'{stats["added"]} targets imported to campaign {campaign.name}', 
                          get_client_ip())
        
        return jsonify({
            'success': True,
            'stats': stats,
            'message': f'Import complete: {stats["added"]} added, {stats["skipped"]} skipped'
        })
        
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error in bulk import: {str(e)}")
        return jsonify({'error': 'Bulk import failed'}), 500