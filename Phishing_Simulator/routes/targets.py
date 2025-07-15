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

# FIXED: Added url_prefix='/admin/targets' to match app.py registration
bp = Blueprint('targets', __name__, url_prefix='/admin/targets')
logger = logging.getLogger(__name__)


@bp.route('/')
def list_targets():
    """Lista cu toate țintele din sistem"""
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


@bp.route('/create', methods=['POST'])
def create_target():
    """Creează o nouă țintă pentru o campanie"""
    try:
        data = request.get_json()
        
        # Validări de bază
        campaign_id = data.get('campaign_id')
        email = data.get('email', '').strip().lower()
        
        if not campaign_id:
            return jsonify({'error': 'Campaign ID is required'}), 400
        
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        # Verifică dacă campania există
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Validează email-ul
        try:
            validate_email(email)
        except ValidationError as e:
            return jsonify({'error': f'Invalid email: {str(e)}'}), 400
        
        # Verifică duplicatele în campania respectivă
        existing = Target.get_by_email_and_campaign(email, campaign_id)
        if existing:
            return jsonify({'error': f'Target with email {email} already exists in this campaign'}), 400
        
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
                return jsonify({'error': f'Invalid phone: {str(e)}'}), 400
        
        # Creează ținta folosind CampaignService
        target = CampaignService.add_single_target(campaign_id, email, **target_data)
        
        return jsonify({
            'success': True,
            'target': target.to_dict(),
            'message': f'Target {email} added to campaign "{campaign.name}"'
        })
        
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating target: {str(e)}")
        return jsonify({'error': 'Failed to create target'}), 500


@bp.route('/<int:target_id>')
def get_target(target_id):
    """Returnează detaliile complete ale unei ținte"""
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
        
        return jsonify({
            'target': target.to_dict(),
            'campaign': campaign_info,
            'tracking_summary': tracking_summary,
            'credentials': credentials_info
        })
        
    except Exception as e:
        logger.error(f"Error getting target {target_id}: {str(e)}")
        return jsonify({'error': 'Target not found'}), 404


@bp.route('/<int:target_id>', methods=['PUT'])
def update_target(target_id):
    """Actualizează informațiile unei ținte"""
    try:
        target = Target.query.get_or_404(target_id)
        data = request.get_json()
        
        # Câmpurile care pot fi actualizate
        updatable_fields = ['first_name', 'last_name', 'company', 'position', 'phone', 'notes']
        update_data = {}
        
        for field in updatable_fields:
            if field in data:
                value = data[field]
                if value:
                    value = sanitize_input(value.strip())
                update_data[field] = value
        
        # Validare specială pentru telefon
        if 'phone' in update_data and update_data['phone']:
            try:
                validate_phone_number(update_data['phone'])
            except ValidationError as e:
                return jsonify({'error': f'Invalid phone: {str(e)}'}), 400
        
        # Actualizează ținta
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


@bp.route('/<int:target_id>', methods=['DELETE'])
def delete_target(target_id):
    """Șterge o țintă din sistem"""
    try:
        target = Target.query.get_or_404(target_id)
        target_email = target.email
        campaign_name = target.campaign.name if target.campaign else 'Unknown'
        
        # Șterge ținta (cascade va șterge automat tracking și credentials)
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


@bp.route('/bulk-import', methods=['POST'])
def bulk_import_targets():
    """Import în masă al țintelor din CSV"""
    try:
        data = request.get_json()
        
        campaign_id = data.get('campaign_id')
        csv_content = data.get('csv_content', '')
        skip_duplicates = data.get('skip_duplicates', True)
        
        if not campaign_id:
            return jsonify({'error': 'Campaign ID is required'}), 400
        
        if not csv_content:
            return jsonify({'error': 'CSV content is required'}), 400
        
        # Verifică dacă campania există
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Folosește CampaignService pentru import
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


@bp.route('/export')
def export_targets():
    """Export ținte în format CSV"""
    try:
        campaign_id = request.args.get('campaign_id', type=int)
        include_sensitive = request.args.get('include_sensitive', 'false').lower() == 'true'
        
        if campaign_id:
            # Export pentru o campanie specifică
            targets = Target.query.filter_by(campaign_id=campaign_id).all()
            campaign = Campaign.query.get(campaign_id)
            filename_prefix = f"targets_{campaign.name.replace(' ', '_')}" if campaign else f"targets_campaign_{campaign_id}"
        else:
            # Export toate țintele
            targets = Target.query.all()
            filename_prefix = "all_targets"
        
        # Generează CSV
        output = io.StringIO()
        
        # Câmpurile de bază
        fieldnames = [
            'email', 'first_name', 'last_name', 'company', 'position', 'phone',
            'campaign_name', 'status', 'engagement_score', 'email_sent', 'sms_sent',
            'clicked_link', 'entered_credentials', 'created_at', 'last_activity'
        ]
        
        # Adaugă câmpuri sensibile dacă e cerut
        if include_sensitive:
            fieldnames.extend(['notes', 'ip_addresses', 'user_agents'])
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for target in targets:
            row = {
                'email': target.email,
                'first_name': target.first_name or '',
                'last_name': target.last_name or '',
                'company': target.company or '',
                'position': target.position or '',
                'phone': target.phone or '',
                'campaign_name': target.campaign.name if target.campaign else '',
                'status': target.status_display,
                'engagement_score': target.engagement_score,
                'email_sent': target.email_sent,
                'sms_sent': target.sms_sent,
                'clicked_link': target.clicked_link,
                'entered_credentials': target.entered_credentials,
                'created_at': target.created_at.isoformat() if target.created_at else '',
                'last_activity': target.last_activity.isoformat() if target.last_activity else ''
            }
            
            # Adaugă date sensibile dacă e cerut
            if include_sensitive:
                row['notes'] = target.notes or ''
                # Colectează IP-uri și user agents din tracking
                ips = set()
                user_agents = set()
                for event in target.tracking_events:
                    if event.ip_address:
                        ips.add(event.ip_address)
                    if event.user_agent:
                        user_agents.add(event.user_agent[:50])  # Truncated
                
                row['ip_addresses'] = '; '.join(ips)
                row['user_agents'] = '; '.join(user_agents)
            
            writer.writerow(row)
        
        csv_content = output.getvalue()
        output.close()
        
        return jsonify({
            'success': True,
            'csv_content': csv_content,
            'filename': f'{filename_prefix}.csv',
            'count': len(targets),
            'include_sensitive': include_sensitive
        })
        
    except Exception as e:
        logger.error(f"Error exporting targets: {str(e)}")
        return jsonify({'error': 'Export failed'}), 500


@bp.route('/stats')
def get_targets_stats():
    """Statistici detaliate despre ținte"""
    try:
        from sqlalchemy import func
        
        # Statistici generale
        total_targets = Target.query.count()
        
        # Statistici pe status (compute manual)
        all_targets = Target.query.all()
        status_stats = {
            'pending': len([t for t in all_targets if t.status == 'pending']),
            'contacted': len([t for t in all_targets if t.status == 'contacted']),
            'clicked_link': len([t for t in all_targets if t.status == 'clicked_link']),
            'credentials_entered': len([t for t in all_targets if t.status == 'credentials_entered'])
        }
        
        # Top companii
        company_stats = db.session.query(
            Target.company,
            func.count(Target.id).label('count')
        ).filter(Target.company.isnot(None))\
         .group_by(Target.company)\
         .order_by(func.count(Target.id).desc())\
         .limit(10).all()
        
        # Distribuția pe campanii
        campaign_stats = db.session.query(
            Campaign.name,
            func.count(Target.id).label('target_count'),
            Campaign.status
        ).join(Target, Campaign.id == Target.campaign_id)\
         .group_by(Campaign.id)\
         .order_by(func.count(Target.id).desc()).all()
        
        # Engagement statistics
        engagement_stats = {
            'avg_engagement_score': db.session.query(func.avg(Target.engagement_score)).scalar() or 0,
            'high_engagement': len([t for t in all_targets if t.engagement_score >= 75]),
            'medium_engagement': len([t for t in all_targets if 25 <= t.engagement_score < 75]),
            'low_engagement': len([t for t in all_targets if t.engagement_score < 25])
        }
        
        return jsonify({
            'total_targets': total_targets,
            'status_distribution': status_stats,
            'top_companies': [
                {'company': comp.company, 'count': comp.count}
                for comp in company_stats
            ],
            'campaign_distribution': [
                {
                    'campaign_name': camp.name,
                    'target_count': camp.target_count,
                    'campaign_status': camp.status
                }
                for camp in campaign_stats
            ],
            'engagement_stats': engagement_stats
        })
        
    except Exception as e:
        logger.error(f"Error getting targets stats: {str(e)}")
        return jsonify({'error': 'Failed to load statistics'}), 500


@bp.route('/search')
def search_targets():
    """Caută ținte după diferite criterii"""
    try:
        query = request.args.get('q', '').strip()
        campaign_id = request.args.get('campaign_id', type=int)
        limit = int(request.args.get('limit', 20))
        
        if not query:
            return jsonify({'targets': [], 'query': query, 'count': 0})
        
        # Construiește query-ul de căutare
        search_query = Target.query.filter(
            db.or_(
                Target.email.contains(query),
                Target.first_name.contains(query),
                Target.last_name.contains(query),
                Target.company.contains(query),
                Target.position.contains(query)
            )
        )
        
        # Filtrează după campanie dacă e specificată
        if campaign_id:
            search_query = search_query.filter_by(campaign_id=campaign_id)
        
        # Execută căutarea cu limit
        targets = search_query.order_by(Target.created_at.desc()).limit(limit).all()
        
        return jsonify({
            'targets': [t.to_dict() for t in targets],
            'query': query,
            'count': len(targets),
            'campaign_filter': campaign_id
        })
        
    except Exception as e:
        logger.error(f"Error searching targets: {str(e)}")
        return jsonify({'error': 'Search failed'}), 500


# === HELPER ROUTES ===

@bp.route('/validate-csv', methods=['POST'])
def validate_csv():
    """Validează un CSV înainte de import"""
    try:
        data = request.get_json()
        csv_content = data.get('csv_content', '')
        
        if not csv_content:
            return jsonify({'error': 'CSV content is required'}), 400
        
        # Parse CSV și validează formatul
        from utils.validators import validate_csv_format
        
        try:
            validate_csv_format(csv_content, required_columns=['email'])
            
            # Parse și analizează conținutul
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)
            
            rows = list(reader)
            valid_emails = 0
            invalid_emails = []
            
            for i, row in enumerate(rows, 1):
                email = row.get('email', '').strip()
                if email:
                    try:
                        validate_email(email)
                        valid_emails += 1
                    except ValidationError:
                        invalid_emails.append(f"Row {i}: {email}")
            
            return jsonify({
                'valid': True,
                'total_rows': len(rows),
                'valid_emails': valid_emails,
                'invalid_emails': invalid_emails[:10],  # Primele 10 erori
                'headers': list(reader.fieldnames) if hasattr(reader, 'fieldnames') else []
            })
            
        except ValidationError as e:
            return jsonify({'valid': False, 'error': str(e)}), 400
        
    except Exception as e:
        logger.error(f"Error validating CSV: {str(e)}")
        return jsonify({'error': 'CSV validation failed'}), 500