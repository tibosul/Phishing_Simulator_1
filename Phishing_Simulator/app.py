#!/usr/bin/env python3
"""
Phishing Simulator - Flask Application
Entry point pentru aplicația de simulare phishing
"""

import os
import sys
import logging
from datetime import datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import configuration
from config import config

# Import database utilities
from utils.database import db, init_db, create_initial_data

# Import all models to ensure they're registered with SQLAlchemy
from models.campaign import Campaign
from models.target import Target
from models.template import Template
from models.tracking import Tracking
from models.credential import Credential

# Import route blueprints
from routes.campaigns import bp as campaigns_bp
from routes.dashboard import bp as dashboard_bp
from routes.targets import bp as targets_bp
from routes.templates import bp as templates_bp
from routes.webhook import bp as webhook_bp
from routes.fake_revolut import bp as fake_revolut_bp

# Import services
from services.campaign_service import CampaignService
from utils.helpers import get_client_ip, log_security_event


def create_app(config_name=None):
    """
    Application factory pentru crearea instanței Flask
    
    Args:
        config_name: Numele configurației de folosit (development, production, testing)
        
    Returns:
        Flask: Instanța aplicației configurată
    """
    # Creează instanța Flask
    app = Flask(__name__)
    
    # Determină configurația
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    # Încarcă configurația
    app.config.from_object(config[config_name])
    
    # Configurează logging
    configure_logging(app)
    
    # Inițializează extensiile
    init_extensions(app)
    
    # Înregistrează blueprint-urile
    register_blueprints(app)
    
    # Înregistrează error handlers
    register_error_handlers(app)
    
    # Înregistrează context processors
    register_context_processors(app)
    
    # Înregistrează comenzile CLI
    register_cli_commands(app)
    
    # Log aplicația pornită
    app.logger.info(f"Phishing Simulator started in {config_name} mode")
    
    return app


def configure_logging(app):
    """Configurează logging pentru aplicație"""
    if not app.debug and not app.testing:
        # Configurare logging pentru producție
        if app.config.get('LOG_FILE'):
            file_handler = logging.FileHandler(app.config['LOG_FILE'])
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s '
                '[in %(pathname)s:%(lineno)d]'
            ))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Phishing Simulator startup')


def init_extensions(app):
    """Inițializează extensiile Flask"""
    # Inițializează baza de date
    init_db(app)
    
    # Creează tabelele în contextul aplicației
    with app.app_context():
        try:
            db.create_all()
            create_initial_data()
            app.logger.info("Database initialized successfully")
        except Exception as e:
            app.logger.error(f"Database initialization failed: {str(e)}")
            raise


def register_blueprints(app):
    """Înregistrează toate blueprint-urile"""
    
    # Dashboard (pagina principală)
    app.register_blueprint(dashboard_bp, url_prefix='/admin')
    
    # Campaigns management
    app.register_blueprint(campaigns_bp, url_prefix='/admin/campaigns')
    
    # Targets management  
    app.register_blueprint(targets_bp, url_prefix='/admin/targets')
    
    # Templates management
    app.register_blueprint(templates_bp, url_prefix='/admin/templates')
    
    # Webhook endpoints pentru tracking
    app.register_blueprint(webhook_bp, url_prefix='/webhook')
    
    # Site-ul fake Revolut
    app.register_blueprint(fake_revolut_bp, url_prefix='/revolut')
    
    app.logger.info("All blueprints registered successfully")


def register_error_handlers(app):
    """Înregistrează handler-ii pentru erori"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        """Handler pentru erroarea 404"""
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Resource not found'}), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handler pentru erroarea 500"""
        db.session.rollback()
        app.logger.error(f'Server Error: {error}')
        
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        """Handler pentru erroarea 403"""
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Forbidden'}), 403
        return render_template('errors/403.html'), 403


def register_context_processors(app):
    """Înregistrează context processors pentru template-uri"""
    
    @app.context_processor
    def inject_app_info():
        """Injectează informații despre aplicație în toate template-urile"""
        return {
            'app_name': app.config.get('APP_NAME', 'Phishing Simulator'),
            'app_version': app.config.get('APP_VERSION', '1.0.0'),
            'current_year': datetime.now().year,
            'is_debug': app.debug
        }
    
    @app.context_processor
    def inject_dashboard_stats():
        """Injectează statistici rapide pentru navigation"""
        try:
            stats = CampaignService.get_dashboard_stats()
            return {'nav_stats': stats}
        except Exception as e:
            app.logger.error(f"Error getting dashboard stats: {str(e)}")
            return {'nav_stats': {}}


def register_cli_commands(app):
    """Înregistrează comenzi CLI pentru management"""
    
    @app.cli.command('init-db')
    def init_db_command():
        """Inițializează baza de date"""
        try:
            db.create_all()
            create_initial_data()
            print("Database initialized successfully!")
        except Exception as e:
            print(f"Error initializing database: {str(e)}")
    
    @app.cli.command('create-admin')
    def create_admin_command():
        """Creează un utilizator admin (pentru viitor)"""
        print("Admin user creation not implemented yet")
    
    @app.cli.command('reset-db')
    def reset_db_command():
        """Resetează baza de date (ATENȚIE: șterge toate datele!)"""
        if input("Are you sure you want to reset the database? (yes/no): ") == 'yes':
            try:
                db.drop_all()
                db.create_all()
                create_initial_data()
                print("Database reset successfully!")
            except Exception as e:
                print(f"Error resetting database: {str(e)}")
        else:
            print("Database reset cancelled")
    
    @app.cli.command('export-data')
    def export_data_command():
        """Exportă toate datele într-un fișier backup"""
        print("Data export not implemented yet")


# ===== ROUTE-URI PRINCIPALE =====

@app.route('/')
def index():
    """Pagina principală - redirectează la dashboard"""
    return redirect(url_for('dashboard.index'))


@app.route('/health')
def health_check():
    """Health check endpoint pentru monitoring"""
    try:
        # Verifică conexiunea la baza de date
        db.session.execute('SELECT 1')
        
        # Statistici rapide
        total_campaigns = Campaign.query.count()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected',
            'total_campaigns': total_campaigns,
            'version': app.config.get('APP_VERSION', '1.0.0')
        })
    except Exception as e:
        app.logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }), 500


@app.route('/api/stats')
def api_stats():
    """API endpoint pentru statistici generale"""
    try:
        stats = CampaignService.get_dashboard_stats()
        
        # Adaugă informații suplimentare
        stats.update({
            'database_stats': {
                'campaigns': Campaign.query.count(),
                'targets': Target.query.count(),
                'templates': Template.query.count(),
                'tracking_events': Tracking.query.count(),
                'credentials': Credential.query.count()
            },
            'system_info': {
                'version': app.config.get('APP_VERSION', '1.0.0'),
                'environment': os.environ.get('FLASK_ENV', 'development'),
                'uptime': 'Not implemented'  # TODO: implementează uptime tracking
            }
        })
        
        return jsonify(stats)
    except Exception as e:
        app.logger.error(f"Error getting API stats: {str(e)}")
        return jsonify({'error': 'Failed to get statistics'}), 500


# ===== MIDDLEWARE =====

@app.before_request
def before_request():
    """Se execută înainte de fiecare request"""
    # Log request-urile importante
    if not request.path.startswith('/static/'):
        app.logger.debug(f"Request: {request.method} {request.path} from {get_client_ip()}")
    
    # Setează header-e de securitate
    if request.endpoint and request.endpoint.startswith('fake_revolut'):
        # Pentru site-ul fake, nu vrem header-e de securitate prea stricte
        pass
    else:
        # Pentru admin panel, setează header-e de securitate
        pass


@app.after_request
def after_request(response):
    """Se execută după fiecare request"""
    # Adaugă header-e de securitate pentru admin panel
    if request.endpoint and not request.endpoint.startswith('fake_revolut'):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # CORS pentru API endpoints
    if request.path.startswith('/api/'):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    
    return response


# ===== CREAREA APLICAȚIEI =====

# Creează aplicația
app = create_app()

# Înregistrează route-urile principale (pentru compatibilitate cu blueprint-urile)
app.add_url_rule('/', 'index', index)
app.add_url_rule('/health', 'health_check', health_check)
app.add_url_rule('/api/stats', 'api_stats', api_stats)


if __name__ == '__main__':
    """
    Rulează aplicația în mod development
    Pentru producție, folosește un WSGI server (gunicorn, uWSGI, etc.)
    """
    try:
        # Verifică că toate dependențele sunt instalate
        import flask_sqlalchemy
        print("✓ Flask-SQLAlchemy installed")
        
        # Verifică configurația
        print(f"✓ Running in {app.config.get('ENV', 'unknown')} mode")
        print(f"✓ Database: {app.config.get('SQLALCHEMY_DATABASE_URI', 'not configured')}")
        print(f"✓ Debug mode: {app.debug}")
        
        # Pornește serverul
        port = int(os.environ.get('PORT', 5000))
        host = os.environ.get('HOST', '127.0.0.1')
        
        print(f"\n🚀 Starting Phishing Simulator on http://{host}:{port}")
        print(f"📊 Admin panel: http://{host}:{port}/admin")
        print(f"🔍 Health check: http://{host}:{port}/health")
        print("\n⚠️  Educational purposes only - Use responsibly!")
        
        app.run(
            host=host,
            port=port,
            debug=app.debug,
            threaded=True
        )
        
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down Phishing Simulator...")
        log_security_event('application_shutdown', 'Application stopped by user')
        
    except Exception as e:
        print(f"\n❌ Failed to start application: {str(e)}")
        app.logger.error(f"Application startup failed: {str(e)}")
        sys.exit(1)