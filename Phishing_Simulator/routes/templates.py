from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from models.template import Template
from services.email_service import EmailService
from services.sms_service import SMSService
from utils.validators import ValidationError
from utils.helpers import get_client_ip, log_security_event
from utils.database import db
import logging

# Crearea Blueprint-ului pentru template-uri
bp = Blueprint('templates', __name__)
logger = logging.getLogger(__name__)


@bp.route('/')
def list_templates():
    """Lista cu toate template-urile"""
    try:
        # Parametri de căutare și filtrare
        search_query = request.args.get('q', '').strip()
        type_filter = request.args.get('type', '')  # email, sms
        category_filter = request.args.get('category', '')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # Construiește query-ul de bază
        templates_query = Template.query.filter_by(is_active=True)
        
        # Aplică filtrele
        if search_query:
            templates_query = templates_query.filter(
                db.or_(
                    Template.name.contains(search_query),
                    Template.description.contains(search_query),
                    Template.content.contains(search_query)
                )
            )
        
        if type_filter:
            templates_query = templates_query.filter_by(type=type_filter)
        
        if category_filter:
            templates_query = templates_query.filter_by(category=category_filter)
        
        # Paginare și ordonare
        templates = templates_query.order_by(
            Template.usage_count.desc(),
            Template.created_at.desc()
        ).paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        # Statistici pentru dashboard
        stats = {
            'total': Template.query.filter_by(is_active=True).count(),
            'email': Template.query.filter_by(type='email', is_active=True).count(),
            'sms': Template.query.filter_by(type='sms', is_active=True).count(),
            'categories': [cat[0] for cat in Template.query.with_entities(Template.category).filter(Template.category.isnot(None)).distinct().all()]
        }
        
        # Template-uri populare
        popular_templates = Template.get_popular_templates(5)
        high_success_templates = Template.get_high_success_templates(5)
        
        return jsonify({
            'templates': [t.to_dict() for t in templates.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': templates.total,
                'pages': templates.pages,
                'has_prev': templates.has_prev,
                'has_next': templates.has_next
            },
            'stats': stats,
            'popular_templates': [t.to_dict() for t in popular_templates],
            'high_success_templates': [t.to_dict() for t in high_success_templates],
            'filters': {
                'search_query': search_query,
                'type_filter': type_filter,
                'category_filter': category_filter
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing templates: {str(e)}")
        return jsonify({'error': 'Failed to load templates'}), 500


@bp.route('/create', methods=['POST'])
def create_template():
    """Creează un nou template"""
    try:
        data = request.get_json()
        
        # Validări de bază
        required_fields = ['name', 'type', 'content']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Extrage datele
        name = data['name'].strip()
        template_type = data['type']
        content = data['content'].strip()
        subject = data.get('subject', '').strip() if template_type == 'email' else None
        description = data.get('description', '').strip()
        category = data.get('category', '').strip()
        difficulty_level = data.get('difficulty_level', 'medium')
        language = data.get('language', 'en')
        
        # Validări specifice
        if template_type not in ['email', 'sms']:
            return jsonify({'error': 'Invalid template type'}), 400
        
        if template_type == 'email' and not subject:
            return jsonify({'error': 'Subject is required for email templates'}), 400
        
        # Verifică unicitatea numelui
        existing = Template.query.filter_by(name=name).first()
        if existing:
            return jsonify({'error': f'Template with name "{name}" already exists'}), 400
        
        # Creează template-ul
        template = Template(
            name=name,
            type=template_type,
            content=content,
            subject=subject,
            description=description,
            category=category,
            difficulty_level=difficulty_level,
            language=language
        )
        
        # Validează și salvează
        template.validate()
        db.session.add(template)
        db.session.commit()
        
        log_security_event('template_created', f'Template "{template.name}" created', get_client_ip())
        
        return jsonify({
            'success': True,
            'template': template.to_dict(),
            'message': f'Template "{template.name}" created successfully'
        })
        
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating template: {str(e)}")
        return jsonify({'error': 'Failed to create template'}), 500


@bp.route('/<int:template_id>')
def get_template(template_id):
    """Returnează detaliile unui template"""
    try:
        template = Template.query.get_or_404(template_id)
        
        # Statistici de utilizare - queries pe tracking/campaigns
        from models.tracking import Tracking
        from sqlalchemy import func
        
        usage_stats = {
            'total_usage': template.usage_count,
            'success_rate': template.success_rate,
            'campaigns_used': db.session.query(func.count(func.distinct(Tracking.campaign_id)))\
                .filter(Tracking.event_data.contains(f'"template_id": {template.id}')).scalar() or 0,
            'last_used': db.session.query(func.max(Tracking.timestamp))\
                .filter(Tracking.event_data.contains(f'"template_id": {template.id}')).scalar()
        }
        
        return jsonify({
            'template': template.to_dict(),
            'usage_stats': usage_stats
        })
        
    except Exception as e:
        logger.error(f"Error getting template {template_id}: {str(e)}")
        return jsonify({'error': 'Template not found'}), 404


@bp.route('/<int:template_id>', methods=['PUT'])
def update_template(template_id):
    """Actualizează un template existent"""
    try:
        template = Template.query.get_or_404(template_id)
        data = request.get_json()
        
        # Actualizează câmpurile
        if 'name' in data:
            new_name = data['name'].strip()
            if new_name != template.name:
                # Verifică unicitatea noului nume
                existing = Template.query.filter(
                    Template.name == new_name,
                    Template.id != template_id
                ).first()
                if existing:
                    return jsonify({'error': f'Template name "{new_name}" already exists'}), 400
                template.name = new_name
        
        updatable_fields = ['subject', 'content', 'description', 'category', 'difficulty_level', 'language']
        for field in updatable_fields:
            if field in data:
                setattr(template, field, data[field])
        
        # Validează și salvează
        template.validate()
        db.session.commit()
        
        log_security_event('template_updated', f'Template "{template.name}" updated', get_client_ip())
        
        return jsonify({
            'success': True,
            'template': template.to_dict(),
            'message': f'Template "{template.name}" updated successfully'
        })
        
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating template {template_id}: {str(e)}")
        return jsonify({'error': 'Failed to update template'}), 500


@bp.route('/<int:template_id>', methods=['DELETE'])
def delete_template(template_id):
    """Șterge un template (soft delete)"""
    try:
        template = Template.query.get_or_404(template_id)
        template_name = template.name
        
        # Soft delete - marchează ca inactiv
        template.is_active = False
        db.session.commit()
        
        log_security_event('template_deleted', f'Template "{template_name}" deleted', get_client_ip())
        
        return jsonify({
            'success': True,
            'message': f'Template "{template_name}" deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting template {template_id}: {str(e)}")
        return jsonify({'error': 'Failed to delete template'}), 500


@bp.route('/<int:template_id>/clone', methods=['POST'])
def clone_template(template_id):
    """Clonează un template"""
    try:
        template = Template.query.get_or_404(template_id)
        data = request.get_json() or {}
        
        new_name = data.get('new_name', f"{template.name} - Copy")
        
        # Verifică unicitatea numelui
        existing = Template.query.filter_by(name=new_name).first()
        if existing:
            return jsonify({'error': f'Template name "{new_name}" already exists'}), 400
        
        # Clonează template-ul
        cloned_template = template.clone(new_name)
        db.session.add(cloned_template)
        db.session.commit()
        
        log_security_event('template_cloned', f'Template "{template.name}" cloned as "{new_name}"', get_client_ip())
        
        return jsonify({
            'success': True,
            'template': cloned_template.to_dict(),
            'message': f'Template cloned as "{new_name}"'
        })
        
    except Exception as e:
        logger.error(f"Error cloning template {template_id}: {str(e)}")
        return jsonify({'error': 'Failed to clone template'}), 500


@bp.route('/<int:template_id>/test', methods=['POST'])
def test_template(template_id):
    """Trimite un test email/SMS cu template-ul"""
    try:
        template = Template.query.get_or_404(template_id)
        data = request.get_json()
        
        test_target = data.get('test_target', '').strip()
        if not test_target:
            return jsonify({'error': 'Test target (email/phone) is required'}), 400
        
        if template.is_email:
            # Test email folosind EmailService
            email_service = EmailService()
            success = email_service.send_test_email(template.name, test_target)
            
        elif template.is_sms:
            # Test SMS folosind SMSService
            sms_service = SMSService()
            success = sms_service.send_test_sms(template.content, test_target)
        else:
            return jsonify({'error': 'Invalid template type'}), 400
        
        if success:
            log_security_event('template_tested', f'Template "{template.name}" tested to {test_target}', get_client_ip())
            return jsonify({
                'success': True,
                'message': f'Test {template.type} sent to {test_target}'
            })
        else:
            return jsonify({'error': f'Failed to send test {template.type}'}), 500
            
    except Exception as e:
        logger.error(f"Error testing template {template_id}: {str(e)}")
        return jsonify({'error': 'Failed to send test message'}), 500


@bp.route('/categories')
def get_categories():
    """Returnează toate categoriile de template-uri"""
    try:
        categories = db.session.query(Template.category)\
            .filter(Template.category.isnot(None), Template.is_active == True)\
            .distinct().all()
        
        return jsonify({
            'categories': [cat[0] for cat in categories if cat[0]]
        })
        
    except Exception as e:
        logger.error(f"Error getting categories: {str(e)}")
        return jsonify({'error': 'Failed to load categories'}), 500


@bp.route('/search')
def search_templates():
    """Caută template-uri după query"""
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({'templates': []})
        
        templates = Template.search_templates(query)
        
        return jsonify({
            'templates': [t.to_dict() for t in templates],
            'query': query,
            'count': len(templates)
        })
        
    except Exception as e:
        logger.error(f"Error searching templates: {str(e)}")
        return jsonify({'error': 'Search failed'}), 500


@bp.route('/stats')
def get_template_stats():
    """Returnează statistici generale despre template-uri"""
    try:
        stats = {
            'total_templates': Template.query.filter_by(is_active=True).count(),
            'email_templates': Template.get_by_type('email'),
            'sms_templates': Template.get_by_type('sms'),
            'popular_templates': [t.to_dict() for t in Template.get_popular_templates(10)],
            'high_success_templates': [t.to_dict() for t in Template.get_high_success_templates(10)],
            'categories': Template.query.with_entities(Template.category)\
                .filter(Template.category.isnot(None), Template.is_active == True)\
                .distinct().count()
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting template stats: {str(e)}")
        return jsonify({'error': 'Failed to load statistics'}), 500