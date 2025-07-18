"""
Routes package pentru Phishing Simulator

Conține toate blueprint-urile Flask:
- campaigns: Gestionarea campaniilor ✓ (IMPLEMENTED)
- dashboard: Dashboard-ul administrativ ✓ (STUB)
- templates: Gestionarea template-urilor ✓ (STUB)
- targets: Gestionarea țintelor ✓ (STUB)
- webhook: Endpoint-uri pentru tracking ✓ (STUB)
- fake_revolut: Site-ul fake Revolut ✓ (STUB)
"""

# Import toate blueprint-urile
from .campaigns import bp as campaigns_bp
from .dashboard import bp as dashboard_bp
from .templates import bp as templates_bp
from .targets import bp as targets_bp
from .webhook import bp as webhook_bp
from .fake_revolut import bp as fake_revolut_bp
from .debug import debug_bp

__all__ = [
    'campaigns_bp',
    'dashboard_bp',
    'templates_bp', 
    'targets_bp',
    'webhook_bp',
    'fake_revolut_bp',
    'debug_bp'
]