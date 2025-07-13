# ===========================================
# routes/__init__.py
# ===========================================

"""
Routes package pentru Phishing Simulator

Conține toate blueprint-urile Flask:
- dashboard: Dashboard-ul administrativ
- campaigns: Gestionarea campaniilor
- templates: Gestionarea template-urilor
- targets: Gestionarea țintelor
- webhook: Endpoint-uri pentru tracking
- fake_revolut: Site-ul fake Revolut
"""

from .dashboard import bp as dashboard_bp
from .campaigns import bp as campaigns_bp
from .templates import bp as templates_bp
from .targets import bp as targets_bp
from .webhook import bp as webhook_bp
from .fake_revolut import bp as fake_revolut_bp

__all__ = [
    'dashboard_bp',
    'campaigns_bp',
    'templates_bp', 
    'targets_bp',
    'webhook_bp',
    'fake_revolut_bp'
]
