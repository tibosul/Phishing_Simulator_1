import os
from datetime import timedelta

class Config:
    """Configurări de bază pentru aplicația Flask"""
    
    # === FLASK CORE SETTINGS ===
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = True
    TESTING = False
    
    # === DATABASE SETTINGS ===
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///database.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False  # Set True for SQL debugging
    
    # === SESSION SETTINGS ===
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = False  # Set True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # === EMAIL SETTINGS ===
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'noreply@phishing-simulator.local'
    
    # === SMS SETTINGS ===
    SMS_API_KEY = os.environ.get('SMS_API_KEY')
    SMS_API_SECRET = os.environ.get('SMS_API_SECRET')
    SMS_FROM_NUMBER = os.environ.get('SMS_FROM_NUMBER') or '+40700000000'
    
    # === OLLAMA AI SETTINGS ===
    OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL') or 'http://localhost:11434'
    OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL') or 'llama2'
    OLLAMA_TIMEOUT = int(os.environ.get('OLLAMA_TIMEOUT') or 30)
    
    # === APPLICATION SETTINGS ===
    APP_NAME = 'Phishing Simulator'
    APP_VERSION = '1.0.0'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # === TRACKING SETTINGS ===
    TRACKING_PIXEL_ENABLED = True
    WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET') or 'webhook-secret-key'
    BASE_URL = os.environ.get('BASE_URL') or 'http://localhost:5000'
    
    # === SECURITY SETTINGS ===
    WTF_CSRF_ENABLED = True  # Enable CSRF protection
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    BCRYPT_LOG_ROUNDS = 12
    
    # Security headers
    SECURITY_HEADERS_ENABLED = True
    
    # Rate limiting
    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_DEFAULT = 200  # requests per hour for general browsing
    RATE_LIMIT_ADMIN_ENDPOINTS = 50  # for admin operations like creating targets
    
    # === LOGGING SETTINGS ===
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    LOG_FILE = os.environ.get('LOG_FILE') or 'phishing_simulator.log'
    
    # === RATE LIMITING ===
    RATELIMIT_STORAGE_URL = 'memory://'
    RATELIMIT_DEFAULT = "100 per hour"


class DevelopmentConfig(Config):
    """Configurări pentru dezvoltare"""
    DEBUG = True
    SQLALCHEMY_ECHO = True
    WTF_CSRF_ENABLED = False  # Disabled for easier testing


class ProductionConfig(Config):
    """Configurări pentru producție"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_ENABLED = True
    SQLALCHEMY_ECHO = False
    
    # Override cu variabile de mediu obligatorii în producție
    SECRET_KEY = os.environ.get('SECRET_KEY')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    SMS_API_KEY = os.environ.get('SMS_API_KEY')
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Log to stderr in production
        import logging
        from logging import StreamHandler
        file_handler = StreamHandler()
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)


class TestingConfig(Config):
    """Configurări pentru testing"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True


# Dicționar pentru selectarea configurării
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}