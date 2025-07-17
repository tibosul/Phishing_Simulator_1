from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
import io
import csv
from datetime import datetime

from models.campaign import Campaign
from models.target import Target
from services.campaign_service import CampaignService
from utils.validators import ValidationError
from utils.helpers import get_client_ip, log_security_event
import logging

# FIXED: Added url_prefix='/admin/campaigns' to match app.py registration
bp = Blueprint('campaigns', __name__, url_prefix='/admin/campaigns')


@bp.route('/')
def list_campaigns():
    """
    Afișează lista cu toate campaniile
    
    Supports:
    - Search prin query parameter
    - Filtering prin status și type
    - Pagination
    """
    try:
        # Parametri de căutare și filtrare
        search_query = request.args.get('q', '').strip()
        status_filter = request.args.get('status', '')
        type_filter = request.args.get('type', '')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        
        # SIMPLE VERSION - just return empty campaigns for now
        campaigns = []
        
        total_campaigns = 0
        total_pages = 1
        
        # Statistici rapide pentru dashboard
        stats = {
            'total': 0,
            'active': 0,
            'draft': 0,
            'completed': 0
        }
        
        return render_template('admin/campaigns.html',
                     campaigns=campaigns,
                     stats=stats,
                     filters={
                         'search_query': search_query,
                         'status_filter': status_filter,
                         'type_filter': type_filter
                     },
                     page=page,
                     total_pages=total_pages,
                     total_campaigns=total_campaigns)
        
    except Exception as e:
        logging.error(f"Error listing campaigns: {str(e)}")
        flash('Error loading campaigns', 'error')
        return render_template('admin/campaigns.html', 
                             campaigns=[], 
                             stats={},
                             filters={
                                 'search_query': '',
                                 'status_filter': '',
                                 'type_filter': ''
                             },
                             page=1,
                             total_pages=1,
                             total_campaigns=0)


@bp.route('/create', methods=['GET', 'POST'])
def create_campaign():
    """
    Creează o nouă campanie
    
    GET: Afișează formularul
    POST: Procesează crearea campaniei
    """
    if request.method == 'GET':
        return render_template('admin/create_campaign.html')
    
    try:
        # Extrage datele din formular
        name = request.form.get('name', '').strip()
        campaign_type = request.form.get('type', 'email')
        description = request.form.get('description', '').strip()
        
        # Opțiuni avansate
        auto_start = request.form.get('auto_start') == 'on'
        track_opens = request.form.get('track_opens', 'on') == 'on'
        track_clicks = request.form.get('track_clicks', 'on') == 'on'
        
        # Validări de bază
        if not name:
            flash('Campaign name is required', 'error')
            return render_template('admin/create_campaign.html')
        
        if campaign_type not in ['email', 'sms', 'both']:
            flash('Invalid campaign type', 'error')
            return render_template('admin/create_campaign.html')
        
        # Creează campania
        campaign = CampaignService.create_campaign(
            name=name,
            campaign_type=campaign_type,
            description=description,
            auto_start=auto_start,
            track_opens=track_opens,
            track_clicks=track_clicks
        )
        
        flash(f'Campaign "{campaign.name}" created successfully!', 'success')
        log_security_event('campaign_created', f'Campaign "{campaign.name}" created', get_client_ip())
        
        return redirect(url_for('campaigns.view_campaign', campaign_id=campaign.id))
        
    except ValidationError as e:
        flash(str(e), 'error')
        return render_template('admin/create_campaign.html')
    except Exception as e:
        logging.error(f"Error creating campaign: {str(e)}")
        flash('Error creating campaign', 'error')
        return render_template('admin/create_campaign.html')


@bp.route('/<int:campaign_id>')
def view_campaign(campaign_id):
    """
    Afișează detaliile unei campanii
    
    Include:
    - Informații generale
    - Lista țintelor
    - Statistici
    - Recent activity
    """
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        
        # Obține statistici detaliate
        stats = CampaignService.get_campaign_statistics(campaign_id)
        
        # Obține țintele (primele 50 pentru performanță)
        targets = Target.query.filter_by(campaign_id=campaign_id).limit(50).all()
        total_targets = Target.query.filter_by(campaign_id=campaign_id).count()
        
        # Recent activity (ultimele 20 evenimente)
        from models.tracking import Tracking
        recent_activity = Tracking.query.filter_by(campaign_id=campaign_id)\
                                       .order_by(Tracking.timestamp.desc())\
                                       .limit(20).all()
        
        return render_template('admin/campaign_detail.html',
                             campaign=campaign,
                             stats=stats,
                             targets=targets,
                             total_targets=total_targets,
                             recent_activity=recent_activity)
        
    except Exception as e:
        logging.error(f"Error viewing campaign {campaign_id}: {str(e)}")
        flash('Error loading campaign', 'error')
        return redirect(url_for('campaigns.list_campaigns'))


@bp.route('/<int:campaign_id>/edit', methods=['GET', 'POST'])
def edit_campaign(campaign_id):
    """
    Editează o campanie existentă
    """
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        
        if request.method == 'GET':
            return render_template('admin/edit_campaign.html', campaign=campaign)
        
        # POST - actualizează campania
        updates = {}
        
        # Extrage câmpurile din formular
        if 'name' in request.form:
            updates['name'] = request.form['name'].strip()
        
        if 'description' in request.form:
            updates['description'] = request.form['description'].strip()
        
        if 'type' in request.form:
            updates['type'] = request.form['type']
        
        # Opțiuni boolean
        updates['auto_start'] = request.form.get('auto_start') == 'on'
        updates['track_opens'] = request.form.get('track_opens') == 'on'
        updates['track_clicks'] = request.form.get('track_clicks') == 'on'
        
        # Actualizează campania
        updated_campaign = CampaignService.update_campaign(campaign_id, **updates)
        
        flash(f'Campaign "{updated_campaign.name}" updated successfully!', 'success')
        log_security_event('campaign_updated', f'Campaign "{updated_campaign.name}" updated', get_client_ip())
        
        return redirect(url_for('campaigns.view_campaign', campaign_id=campaign_id))
        
    except ValidationError as e:
        flash(str(e), 'error')
        return render_template('admin/edit_campaign.html', campaign=campaign)
    except Exception as e:
        logging.error(f"Error editing campaign {campaign_id}: {str(e)}")
        flash('Error updating campaign', 'error')
        return redirect(url_for('campaigns.view_campaign', campaign_id=campaign_id))


@bp.route('/<int:campaign_id>/delete', methods=['POST'])
def delete_campaign(campaign_id):
    """
    Șterge o campanie
    """
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        campaign_name = campaign.name
        
        # Verifică dacă utilizatorul a confirmat
        if request.form.get('confirm') != 'DELETE':
            flash('Please type DELETE to confirm deletion', 'error')
            return redirect(url_for('campaigns.view_campaign', campaign_id=campaign_id))
        
        # Șterge campania
        force = request.form.get('force') == 'on'
        CampaignService.delete_campaign(campaign_id, force=force)
        
        flash(f'Campaign "{campaign_name}" deleted successfully!', 'success')
        log_security_event('campaign_deleted', f'Campaign "{campaign_name}" deleted', get_client_ip())
        
        return redirect(url_for('campaigns.list_campaigns'))
        
    except ValidationError as e:
        flash(str(e), 'error')
        return redirect(url_for('campaigns.view_campaign', campaign_id=campaign_id))
    except Exception as e:
        logging.error(f"Error deleting campaign {campaign_id}: {str(e)}")
        flash('Error deleting campaign', 'error')
        return redirect(url_for('campaigns.view_campaign', campaign_id=campaign_id))


@bp.route('/<int:campaign_id>/targets/upload', methods=['GET', 'POST'])
def upload_targets(campaign_id):
    """
    Upload CSV cu ținte pentru campanie
    """
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        
        if request.method == 'GET':
            return render_template('admin/upload_targets.html', campaign=campaign)
        
        # Verifică dacă fișierul a fost uploadat
        if 'csv_file' not in request.files:
            flash('No file selected', 'error')
            return render_template('admin/upload_targets.html', campaign=campaign)
        
        file = request.files['csv_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return render_template('admin/upload_targets.html', campaign=campaign)
        
        # Verifică extensia
        if not file.filename.lower().endswith('.csv'):
            flash('Please upload a CSV file', 'error')
            return render_template('admin/upload_targets.html', campaign=campaign)
        
        # Citește conținutul
        csv_content = file.read().decode('utf-8')
        
        # Opțiuni
        skip_duplicates = request.form.get('skip_duplicates') == 'on'
        
        # Procesează CSV-ul
        stats = CampaignService.add_targets_from_csv(
            campaign_id=campaign_id,
            csv_content=csv_content,
            skip_duplicates=skip_duplicates
        )
        
        # Afișează rezultatele
        if stats['added'] > 0:
            flash(f'Successfully added {stats["added"]} targets', 'success')
        
        if stats['skipped'] > 0:
            flash(f'{stats["skipped"]} targets were skipped (duplicates)', 'info')
        
        if stats['errors']:
            flash(f'{len(stats["errors"])} errors occurred during import', 'warning')
            # Poți afișa erorile în template
        
        log_security_event('targets_uploaded', f'{stats["added"]} targets added to campaign "{campaign.name}"', get_client_ip())
        
        return render_template('admin/upload_targets.html', 
                             campaign=campaign, 
                             upload_stats=stats)
        
    except ValidationError as e:
        flash(str(e), 'error')
        return render_template('admin/upload_targets.html', campaign=campaign)
    except Exception as e:
        logging.error(f"Error uploading targets for campaign {campaign_id}: {str(e)}")
        flash('Error processing CSV file', 'error')
        return render_template('admin/upload_targets.html', campaign=campaign)


@bp.route('/<int:campaign_id>/targets/add', methods=['POST'])
def add_single_target(campaign_id):
    """
    Adaugă o singură țintă la campanie (AJAX endpoint)
    """
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        
        # Extrage datele din request
        data = request.get_json() or request.form
        
        email = data.get('email', '').strip()
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        # Date opționale
        target_data = {
            'first_name': data.get('first_name', '').strip(),
            'last_name': data.get('last_name', '').strip(),
            'company': data.get('company', '').strip(),
            'position': data.get('position', '').strip(),
            'phone': data.get('phone', '').strip(),
            'notes': data.get('notes', '').strip()
        }
        
        # Elimină câmpurile goale
        target_data = {k: v for k, v in target_data.items() if v}
        
        # Adaugă ținta
        target = CampaignService.add_single_target(campaign_id, email, **target_data)
        
        log_security_event('target_added', f'Target {email} added to campaign "{campaign.name}"', get_client_ip())
        
        return jsonify({
            'success': True,
            'target': target.to_dict(),
            'message': f'Target {email} added successfully'
        })
        
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Error adding single target to campaign {campaign_id}: {str(e)}")
        return jsonify({'error': 'Error adding target'}), 500


@bp.route('/<int:campaign_id>/export')
def export_campaign(campaign_id):
    """
    Exportă datele campaniei în format CSV
    """
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        
        # Opțiuni de export
        include_credentials = request.args.get('credentials') == 'true'
        
        # Generează CSV-ul
        csv_content = CampaignService.export_campaign_data(
            campaign_id=campaign_id,
            include_credentials=include_credentials
        )
        
        # Creează răspunsul pentru download
        filename = f"campaign_{campaign.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filename = secure_filename(filename)
        
        # Returnează fișierul
        return send_file(
            io.BytesIO(csv_content.encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logging.error(f"Error exporting campaign {campaign_id}: {str(e)}")
        flash('Error exporting campaign data', 'error')
        return redirect(url_for('campaigns.view_campaign', campaign_id=campaign_id))


@bp.route('/<int:campaign_id>/start', methods=['POST'])
def start_campaign(campaign_id):
    """
    Pornește o campanie
    """
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        
        if campaign.start():
            flash(f'Campaign "{campaign.name}" started successfully!', 'success')
            log_security_event('campaign_started', f'Campaign "{campaign.name}" started', get_client_ip())
        else:
            flash('Error starting campaign', 'error')
        
        return redirect(url_for('campaigns.view_campaign', campaign_id=campaign_id))
        
    except Exception as e:
        logging.error(f"Error starting campaign {campaign_id}: {str(e)}")
        flash(f'Error starting campaign: {str(e)}', 'error')
        return redirect(url_for('campaigns.view_campaign', campaign_id=campaign_id))


@bp.route('/<int:campaign_id>/pause', methods=['POST'])
def pause_campaign(campaign_id):
    """
    Pune campania în pauză
    """
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        
        if campaign.pause():
            flash(f'Campaign "{campaign.name}" paused successfully!', 'success')
            log_security_event('campaign_paused', f'Campaign "{campaign.name}" paused', get_client_ip())
        else:
            flash('Error pausing campaign', 'error')
        
        return redirect(url_for('campaigns.view_campaign', campaign_id=campaign_id))
        
    except Exception as e:
        logging.error(f"Error pausing campaign {campaign_id}: {str(e)}")
        flash(f'Error pausing campaign: {str(e)}', 'error')
        return redirect(url_for('campaigns.view_campaign', campaign_id=campaign_id))


@bp.route('/<int:campaign_id>/complete', methods=['POST'])
def complete_campaign(campaign_id):
    """
    Marchează campania ca fiind completată
    """
    try:
        campaign = Campaign.query.get_or_404(campaign_id)
        
        if campaign.complete():
            flash(f'Campaign "{campaign.name}" completed successfully!', 'success')
            log_security_event('campaign_completed', f'Campaign "{campaign.name}" completed', get_client_ip())
        else:
            flash('Error completing campaign', 'error')
        
        return redirect(url_for('campaigns.view_campaign', campaign_id=campaign_id))
        
    except Exception as e:
        logging.error(f"Error completing campaign {campaign_id}: {str(e)}")
        flash(f'Error completing campaign: {str(e)}', 'error')
        return redirect(url_for('campaigns.view_campaign', campaign_id=campaign_id))


# === API ENDPOINTS ===

@bp.route('/api')
def api_list_campaigns():
    """
    API endpoint pentru listarea campaniilor (pentru AJAX)
    """
    try:
        search_query = request.args.get('q', '')
        status_filter = request.args.get('status', '')
        type_filter = request.args.get('type', '')
        
        filters = {}
        if status_filter:
            filters['status'] = status_filter
        if type_filter:
            filters['type'] = type_filter
        
        campaigns = CampaignService.search_campaigns(search_query, filters)
        
        return jsonify({
            'campaigns': [campaign.to_dict() for campaign in campaigns],
            'total': len(campaigns)
        })
        
    except Exception as e:
        logging.error(f"Error in API list campaigns: {str(e)}")
        return jsonify({'error': 'Error loading campaigns'}), 500


@bp.route('/api/<int:campaign_id>/stats')
def api_campaign_stats(campaign_id):
    """
    API endpoint pentru statisticile unei campanii (pentru grafice)
    """
    try:
        stats = CampaignService.get_campaign_statistics(campaign_id)
        return jsonify(stats)
        
    except Exception as e:
        logging.error(f"Error getting campaign stats: {str(e)}")
        return jsonify({'error': 'Error loading statistics'}), 500