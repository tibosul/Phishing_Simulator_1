import os
import logging
from flask import Flask, redirect, url_for, request, jsonify
from config import config
from utils.database import init_db

def create_app(config_name=None):
    """
    Factory pentru crearea aplicației Flask
    
    Args:
        config_name: Numele configurației (development, production, testing)
        
    Returns:
        Flask: Aplicația configurată
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
     
    # Încarcă configurația
    app.config.from_object(config[config_name])
    
    # Configurează logging
    configure_logging(app)
    
    # Configurează security middleware
    configure_security(app)
    
    # Inițializează baza de date
    init_db(app)
    
    # Înregistrează blueprint-urile
    register_blueprints(app)
    
    # Înregistrează error handlers
    register_error_handlers(app)
    
    # Context processors globali
    register_context_processors(app)
    
    # Route principală
    @app.route('/')
    def index():
        """Redirect la dashboard"""
        return redirect(url_for('dashboard.index'))
    
    return app

def configure_logging(app):
    """Configurează logging pentru aplicație"""
    if not app.debug and not app.testing:
        # Configurare pentru producție
        if app.config.get('LOG_FILE'):
            file_handler = logging.FileHandler(app.config['LOG_FILE'])
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
            ))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Phishing Simulator startup')


def configure_security(app):
    """Configurează middleware-ul de securitate"""
    from utils.security import apply_security_headers, rate_limit_check, log_security_event
    from utils.helpers import get_client_ip
    from utils.api_responses import rate_limit_response
    
    @app.before_request
    def security_middleware():
        """Middleware pentru verificări de securitate"""
        
        # Skip security checks for static files
        if request.endpoint == 'static':
            return
        
        # Rate limiting pentru endpoint-uri critice
        if app.config.get('RATE_LIMIT_ENABLED', True):
            # Endpoint-uri cu rate limiting moderat pentru admin
            admin_endpoints = [
                'targets.create_target',
                'templates.create_template',
                'campaigns.create_campaign',
                'targets.upload_targets',
                'targets.api_bulk_import_targets'
            ]
            
            if request.endpoint in admin_endpoints:
                client_ip = get_client_ip()
                # Increased limit for admin operations: 50 requests per hour
                admin_limit = app.config.get('RATE_LIMIT_ADMIN_ENDPOINTS', 50)
                
                allowed, remaining_time = rate_limit_check(client_ip, limit=admin_limit, window=3600)
                if not allowed:
                    log_security_event('rate_limit_exceeded', 
                                     f'Rate limit exceeded for admin endpoint {request.endpoint}',
                                     {'endpoint': request.endpoint, 'ip': client_ip})
                    
                    # Check if this is an AJAX request
                    is_ajax = (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
                              'application/json' in request.headers.get('Accept', ''))
                    
                    if is_ajax:
                        return rate_limit_response(
                            "You're doing that too often. Please wait before trying again.",
                            retry_after=remaining_time
                        )
                    else:
                        # For regular form submissions, use flash message and redirect
                        from flask import flash, redirect, url_for
                        minutes_remaining = max(1, remaining_time // 60)
                        flash(f'You\'re doing that too often. Please wait {minutes_remaining} minute(s) before trying again.', 'warning')
                        return redirect(url_for('dashboard.index'))
            
            # Rate limiting general (less strict for regular browsing)
            else:
                client_ip = get_client_ip()
                general_limit = app.config.get('RATE_LIMIT_DEFAULT', 200)  # Increased from 100
                
                allowed, _ = rate_limit_check(client_ip, limit=general_limit, window=3600)
                if not allowed:
                    # For general rate limiting, just return JSON error
                    return jsonify({'error': 'Rate limit exceeded.'}), 429
    
    @app.after_request
    def security_headers(response):
        """Aplică header-uri de securitate la toate răspunsurile"""
        if app.config.get('SECURITY_HEADERS_ENABLED', True):
            response = apply_security_headers(response)
        return response

def register_blueprints(app):
    """Înregistrează toate blueprint-urile"""
    from routes import (
        campaigns_bp, dashboard_bp, templates_bp, 
        targets_bp, webhook_bp, fake_revolut_bp
    )
    
    # Admin routes
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(templates_bp)
    app.register_blueprint(targets_bp)
    
    # Webhook routes
    app.register_blueprint(webhook_bp)
    
    # Fake site routes
    app.register_blueprint(fake_revolut_bp, url_prefix='/revolut')

def register_error_handlers(app):
    """Înregistrează error handlers globali"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        # Don't redirect Revolut routes to admin dashboard
        if request.path.startswith('/revolut'):
            return redirect(url_for('fake_revolut.home'))
        return redirect(url_for('dashboard.index'))
    
    @app.errorhandler(500)
    def internal_error(error):
        from utils.database import db
        db.session.rollback()
        app.logger.error(f'Server Error: {error}')
        # Don't redirect Revolut routes to admin dashboard
        if request.path.startswith('/revolut'):
            return redirect(url_for('fake_revolut.home'))
        return redirect(url_for('dashboard.index'))
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        app.logger.error(f'Unhandled Exception: {e}')
        # Don't redirect Revolut routes to admin dashboard
        if request.path.startswith('/revolut'):
            return redirect(url_for('fake_revolut.home'))
        return redirect(url_for('dashboard.index'))

def register_context_processors(app):
    """Context processors pentru template-uri"""
    
    @app.context_processor
    def inject_config():
        return {
            'app_name': app.config.get('APP_NAME', 'Phishing Simulator'),
            'app_version': app.config.get('APP_VERSION', '1.0.0')
        }
    
    @app.context_processor
    def inject_sidebar_stats():
        """Injectează statistici pentru sidebar în toate paginile admin"""
        try:
            from datetime import datetime, timedelta
            from models.campaign import Campaign
            from models.target import Target
            from models.credential import Credential
            from models.tracking import Tracking
            
            return {
                'sidebar_stats': {
                    'total_campaigns': Campaign.query.count(),
                    'active_campaigns': Campaign.query.filter_by(status='active').count(),
                    'total_targets': Target.query.count(),
                    'total_credentials': Credential.query.count(),
                    'recent_activity': Tracking.query.filter(
                        Tracking.timestamp >= datetime.utcnow() - timedelta(hours=24)
                    ).count()
                }
            }
        except Exception as e:
            app.logger.error(f"Error getting sidebar stats: {str(e)}")
            return {
                'sidebar_stats': {
                    'total_campaigns': 0,
                    'active_campaigns': 0,
                    'total_targets': 0,
                    'total_credentials': 0,
                    'recent_activity': 0
                }
            }

# Creează aplicația
app = create_app()

# Debug: Print all routes
print("\n=== REGISTERED ROUTES ===")
for rule in app.url_map.iter_rules():
    print(f"{rule.methods} {rule.rule} -> {rule.endpoint}")
print("========================\n")

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )