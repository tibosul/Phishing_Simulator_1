from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from models.template import Template
from services.email_service import EmailService
from services.sms_service import SMSService
from utils.validators import ValidationError
from utils.helpers import get_client_ip, log_security_event, log_admin_action
from utils.security import sanitize_template_content, validate_template_variables
from utils.database import db
import logging

# URL prefix to match app.py registration
bp = Blueprint('templates', __name__, url_prefix='/admin/templates')
logger = logging.getLogger(__name__)


@bp.route('/')
def list_templates():
    """
    FIXED: Lista cu toate template-urile - returnează HTML
    """
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
        
        # FIXED: Return HTML template instead of JSON
        return render_template('admin/templates.html',
                             templates=templates.items,
                             pagination={
                                 'page': page,
                                 'per_page': per_page,
                                 'total': templates.total,
                                 'pages': templates.pages,
                                 'has_prev': templates.has_prev,
                                 'has_next': templates.has_next
                             },
                             stats=stats,
                             popular_templates=popular_templates,
                             high_success_templates=high_success_templates,
                             filters={
                                 'search_query': search_query,
                                 'type_filter': type_filter,
                                 'category_filter': category_filter
                             })
        
    except Exception as e:
        logger.error(f"Error listing templates: {str(e)}")
        flash('Error loading templates', 'error')
        return render_template('admin/templates.html',
                             templates=[],
                             pagination={},
                             stats={},
                             popular_templates=[],
                             high_success_templates=[],
                             filters={})


# API ENDPOINTS (pentru AJAX calls)
@bp.route('/api')
def api_list_templates():
    """API endpoint pentru listarea template-urilor (pentru AJAX)"""
    try:
        search_query = request.args.get('q', '').strip()
        type_filter = request.args.get('type', '')
        category_filter = request.args.get('category', '')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        templates_query = Template.query.filter_by(is_active=True)
        
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
        
        templates = templates_query.order_by(
            Template.usage_count.desc(),
            Template.created_at.desc()
        ).paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        stats = {
            'total': Template.query.filter_by(is_active=True).count(),
            'email': Template.query.filter_by(type='email', is_active=True).count(),
            'sms': Template.query.filter_by(type='sms', is_active=True).count(),
            'categories': [cat[0] for cat in Template.query.with_entities(Template.category).filter(Template.category.isnot(None)).distinct().all()]
        }
        
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


@bp.route('/create', methods=['GET', 'POST'])
def create_template():
    """FIXED: Creează un nou template - GET returnează form, POST procesează"""
    if request.method == 'GET':
        # Return form for creating new template
        return render_template('admin/create_template.html')
    
    try:
        data = request.form.to_dict()
        
        # Validări de bază
        required_fields = ['name', 'type', 'content']
        for field in required_fields:
            if not data.get(field):
                flash(f'{field} is required', 'error')
                return render_template('admin/create_template.html')
        
        # Extrage datele
        name = data['name'].strip()
        template_type = data['type']
        content = data['content'].strip()
        subject = data.get('subject', '').strip() if template_type == 'email' else None
        description = data.get('description', '').strip()
        category = data.get('category', '').strip()
        difficulty_level = data.get('difficulty_level', 'medium')
        language = data.get('language', 'en')
        
        # Sanitizare și validare securizată pentru conținut
        try:
            # Validează variabilele template
            validate_template_variables(content)
            
            # Sanitizează conținutul pentru prevenirea XSS
            content = sanitize_template_content(content, template_type)
            
            # Sanitizează și alte câmpuri
            if subject:
                validate_template_variables(subject)
                subject = sanitize_template_content(subject, 'text')
                
        except ValidationError as e:
            flash(f'Template security validation failed: {str(e)}', 'error')
            return render_template('admin/create_template.html')
        
        # Validări specifice
        if template_type not in ['email', 'sms']:
            flash('Invalid template type', 'error')
            return render_template('admin/create_template.html')
        
        if template_type == 'email' and not subject:
            flash('Subject is required for email templates', 'error')
            return render_template('admin/create_template.html')
        
        # Verifică unicitatea numelui
        existing = Template.query.filter_by(name=name).first()
        if existing:
            flash(f'Template with name "{name}" already exists', 'error')
            return render_template('admin/create_template.html')
        
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
        log_admin_action('create', 'template', template.id, f'Name: {template.name}, Type: {template.type}')
        
        flash(f'Template "{template.name}" created successfully!', 'success')
        return redirect(url_for('templates.view_template', template_id=template.id))
        
    except ValidationError as e:
        flash(str(e), 'error')
        return render_template('admin/create_template.html')
    except Exception as e:
        logger.error(f"Error creating template: {str(e)}")
        flash('Error creating template', 'error')
        return render_template('admin/create_template.html')


@bp.route('/<int:template_id>')
def view_template(template_id):
    """FIXED: Returnează detaliile unui template - HTML page"""
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
        
        return render_template('admin/template_detail.html',
                             template=template,
                             usage_stats=usage_stats)
        
    except Exception as e:
        logger.error(f"Error getting template {template_id}: {str(e)}")
        flash('Template not found', 'error')
        return redirect(url_for('templates.list_templates'))


# API endpoint pentru template details
@bp.route('/api/<int:template_id>')
def api_get_template(template_id):
    """API endpoint pentru detaliile unui template"""
    try:
        template = Template.query.get_or_404(template_id)
        
        # Statistici de utilizare
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


@bp.route('/<int:template_id>/edit', methods=['GET', 'POST'])
def edit_template(template_id):
    """FIXED: Editează un template - GET returnează form, POST procesează"""
    template = Template.query.get_or_404(template_id)
    
    if request.method == 'GET':
        return render_template('admin/edit_template.html', template=template)
    
    try:
        data = request.form.to_dict()
        
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
                    flash(f'Template name "{new_name}" already exists', 'error')
                    return render_template('admin/edit_template.html', template=template)
                template.name = new_name
        
        updatable_fields = ['subject', 'content', 'description', 'category', 'difficulty_level', 'language']
        for field in updatable_fields:
            if field in data:
                value = data[field]
                
                # Sanitizare specială pentru content și subject
                if field in ['content', 'subject']:
                    try:
                        # Validează variabilele template
                        validate_template_variables(value)
                        
                        # Sanitizează conținutul
                        if field == 'content':
                            value = sanitize_template_content(value, template.type)
                        else:  # subject
                            value = sanitize_template_content(value, 'text')
                            
                    except ValidationError as e:
                        flash(f'Template security validation failed for {field}: {str(e)}', 'error')
                        return render_template('admin/edit_template.html', template=template)
                
                setattr(template, field, value)
        
        # Validează și salvează
        template.validate()
        db.session.commit()
        
        log_security_event('template_updated', f'Template "{template.name}" updated', get_client_ip())
        log_admin_action('update', 'template', template.id, f'Name: {template.name}')
        
        flash(f'Template "{template.name}" updated successfully!', 'success')
        return redirect(url_for('templates.view_template', template_id=template_id))
        
    except ValidationError as e:
        flash(str(e), 'error')
        return render_template('admin/edit_template.html', template=template)
    except Exception as e:
        logger.error(f"Error updating template {template_id}: {str(e)}")
        flash('Error updating template', 'error')
        return render_template('admin/edit_template.html', template=template)


@bp.route('/<int:template_id>/delete', methods=['POST'])
def delete_template(template_id):
    """Șterge un template (soft delete)"""
    try:
        template = Template.query.get_or_404(template_id)
        template_name = template.name
        
        # Soft delete - marchează ca inactiv
        template.is_active = False
        db.session.commit()
        
        log_security_event('template_deleted', f'Template "{template_name}" deleted', get_client_ip())
        
        flash(f'Template "{template_name}" deleted successfully!', 'success')
        return redirect(url_for('templates.list_templates'))
        
    except Exception as e:
        logger.error(f"Error deleting template {template_id}: {str(e)}")
        flash('Error deleting template', 'error')
        return redirect(url_for('templates.view_template', template_id=template_id))


@bp.route('/<int:template_id>/clone', methods=['POST'])
def clone_template(template_id):
    """Clonează un template"""
    try:
        template = Template.query.get_or_404(template_id)
        data = request.form.to_dict()
        
        new_name = data.get('new_name', f"{template.name} - Copy")
        
        # Verifică unicitatea numelui
        existing = Template.query.filter_by(name=new_name).first()
        if existing:
            flash(f'Template name "{new_name}" already exists', 'error')
            return redirect(url_for('templates.view_template', template_id=template_id))
        
        # Clonează template-ul
        cloned_template = template.clone(new_name)
        db.session.add(cloned_template)
        db.session.commit()
        
        log_security_event('template_cloned', f'Template "{template.name}" cloned as "{new_name}"', get_client_ip())
        
        flash(f'Template cloned as "{new_name}"!', 'success')
        return redirect(url_for('templates.view_template', template_id=cloned_template.id))
        
    except Exception as e:
        logger.error(f"Error cloning template {template_id}: {str(e)}")
        flash('Error cloning template', 'error')
        return redirect(url_for('templates.view_template', template_id=template_id))


@bp.route('/<int:template_id>/test', methods=['GET', 'POST'])
def test_template(template_id):
    """FIXED: Trimite un test email/SMS cu template-ul"""
    template = Template.query.get_or_404(template_id)
    
    if request.method == 'GET':
        return render_template('admin/test_template.html', template=template)
    
    try:
        data = request.form.to_dict()
        
        test_target = data.get('test_target', '').strip()
        if not test_target:
            flash('Test target (email/phone) is required', 'error')
            return render_template('admin/test_template.html', template=template)
        
        if template.is_email:
            # Test email folosind EmailService
            email_service = EmailService()
            success = email_service.send_test_email(template.name, test_target)
            
        elif template.is_sms:
            # Test SMS folosind SMSService
            sms_service = SMSService()
            success = sms_service.send_test_sms(template.content, test_target)
        else:
            flash('Invalid template type', 'error')
            return render_template('admin/test_template.html', template=template)
        
        if success:
            log_security_event('template_tested', f'Template "{template.name}" tested to {test_target}', get_client_ip())
            flash(f'Test {template.type} sent to {test_target}', 'success')
        else:
            flash(f'Failed to send test {template.type}', 'error')
            
        return render_template('admin/test_template.html', template=template)
            
    except Exception as e:
        logger.error(f"Error testing template {template_id}: {str(e)}")
        flash('Failed to send test message', 'error')
        return render_template('admin/test_template.html', template=template)


@bp.route('/api/categories')
def api_get_categories():
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


@bp.route('/api/search')
def api_search_templates():
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


@bp.route('/api/stats')
def api_get_template_stats():
    """Returnează statistici generale despre template-uri"""
    try:
        stats = {
            'total_templates': Template.query.filter_by(is_active=True).count(),
            'email_templates': len(Template.get_by_type('email')),
            'sms_templates': len(Template.get_by_type('sms')),
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