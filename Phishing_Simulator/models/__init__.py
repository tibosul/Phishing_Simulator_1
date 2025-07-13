# ===========================================
# models/__init__.py
# ===========================================

"""
Models package pentru Phishing Simulator

Conține toate modelele SQLAlchemy pentru baza de date:
- Campaign: Campaniile de phishing
- Target: Țintele/victimele
- Template: Template-urile pentru email/SMS
- Tracking: Evenimentele de tracking
- Credential: Credențialele capturate
"""

from .campaign import Campaign
from .target import Target
from .template import Template
from .tracking import Tracking
from .credential import Credential

__all__ = [
    'Campaign',
    'Target', 
    'Template',
    'Tracking',
    'Credential'
]