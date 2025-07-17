import os
import logging
from flask import Flask, redirect, url_for, request
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