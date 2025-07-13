# ===========================================
# utils/__init__.py
# ===========================================

"""
Utils package pentru Phishing Simulator

Conține utilități și funcții helper:
- database: Setup și management baza de date
- helpers: Funcții generale utile
- validators: Validări pentru input-uri
"""

from .database import db, init_db, create_tables, get_db_stats
from .helpers import (
    generate_unique_id,
    generate_tracking_token,
    build_tracking_url,
    get_client_ip,
    sanitize_input,
    format_datetime
)
from .validators import (
    validate_email,
    validate_phone_number,
    validate_campaign_name,
    ValidationError
)

__all__ = [
    # Database
    'db',
    'init_db', 
    'create_tables',
    'get_db_stats',
    
    # Helpers
    'generate_unique_id',
    'generate_tracking_token',
    'build_tracking_url',
    'get_client_ip',
    'sanitize_input',
    'format_datetime',
    
    # Validators
    'validate_email',
    'validate_phone_number', 
    'validate_campaign_name',
    'ValidationError'
]